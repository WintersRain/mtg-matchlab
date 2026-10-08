"""Opt-in bounded independent-game JVM reuse; same two generic Arena deck inputs."""
import copy
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time
import uuid
import matchlab as m

LIMIT = 8 * 1024 * 1024
GAME_TIMEOUT = 300

def settings(body):
    games = body.get('games', 1)
    seed = body.get('seed', 42)
    if type(games) is not int or not 1 <= games <= 50: raise ValueError('games must be 1..50')
    if type(seed) is not int or not 0 <= seed <= 2**63-games: raise ValueError('Incremented seeds must fit nonnegative signed Java long')
    for key in ('alternate','swap','snapshots'):
        if key in body and type(body[key]) is not bool: raise ValueError(key+' must be boolean')
    return games,seed

def expected_seats(body, index):
    seats = ['seat-a','seat-b']
    if body.get('swap',False) ^ (body.get('alternate',False) and index%2==1): seats.reverse()
    return seats

def marker(line, prefix):
    if not line.startswith(prefix): return None
    value = json.loads(line[len(prefix):])
    if not isinstance(value,dict): raise ValueError('Invalid native lifecycle marker')
    return value

def private_assets(session, res, dirs):
    """Per-session Forge assets dir: symlinked shared res/ plus a private profile.

    Lets concurrent series run without the shared vendor/forge/forge-gui profile symlink.
    Named forge-gui so both asset conventions ("" and "../forge-gui/") resolve here.
    """
    assets = Path(session) / 'forge-gui'
    assets.mkdir()
    (assets / 'res').symlink_to(Path(res).resolve(), target_is_directory=True)
    (assets / 'forge.profile.properties').write_text(
        ''.join(f'{key}={str(value).replace(chr(92), chr(92)*2)}\n' for key, value in dirs.items()))
    return assets

def run_series(body, on_game=None, *, stop_path=None, index=None):
    """Return session plus finalized child summaries; callback is called once per started game.

    stop_path is a trusted caller-owned file, never accepted from a deck/JSON input.
    index is an optional prebuilt card index shared by batch callers (see prepare_pair).
    Every game has a fresh Match/RegisteredPlayers/observer and its own incremented RNG seed.
    This explicit process mode retains Forge's initialized card database and static caches.
    """
    import dashboard as d
    count,seed = settings(body)
    pair = d.prepare_pair(body, index)  # strict both-seat support preflight before spawning anything
    session = m.ROOT/'runtime/reuse'/uuid.uuid4().hex
    session.mkdir(parents=True)
    series = {'schema':1,'process_mode':'reuse-independent','seed_policy':'starting seed + game index; reseed before registering each fresh pair',
              'session_directory':str(session),'status':'invalid','games':[]}
    children = []
    started = time.monotonic()
    proc = None
    try:
        with (m.ROOT/'runtime/run.lock').open('w') as lock, ExitStack() as cleanup:
            # Shared: concurrent series use private asset dirs; legacy single runs still take LOCK_EX.
            fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
            report = d.audit_pair(pair,session/'audit')
            java=m.ROOT/'.local/jdk-17.0.20.1+1/bin/java'
            jar=m.ROOT/'vendor/forge/forge-gui-desktop/target/forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar'
            if not java.is_file() or not jar.is_file(): raise ValueError('Pinned Java/JAR missing')
            jar_hash=m.sha(jar.read_bytes())
            java_version=subprocess.check_output([str(java),'-version'],stderr=subprocess.STDOUT,text=True,timeout=15).strip()
            diff_hash=m.sha(subprocess.check_output(['git','-C',str(m.ROOT/'vendor/forge'),'diff','HEAD','--','*.java']))
            dirs={key:session/sub for key,sub in [('userDir','user'),('cacheDir','cache'),('decksDir','decks'),('decksConstructedDir','decks/constructed')]}
            for directory in dirs.values(): directory.mkdir(parents=True,exist_ok=True)
            home=session/'home';home.mkdir()
            for seat in pair:
                data=(session/'audit'/(seat+'.dck')).read_bytes()
                if m.sha(data)!=report['decks'][seat]['dck_sha256']: raise ValueError('DCK hash mismatch: '+seat)
                (dirs['decksConstructedDir']/(seat+'.dck')).write_bytes(data)
            assets=private_assets(session,m.ROOT/'vendor/forge/forge-gui/res',dirs)
            command=m.build_command(java,jar,home,expected_seats(body,0),seed)
            command[command.index('-n')+1]=str(count)
            env=os.environ.copy()
            for key in ('JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS'):env.pop(key,None)
            env.update(HOME=str(home),XDG_CONFIG_HOME=str(session/'xdg-config'),
                       XDG_CACHE_HOME=str(session/'xdg-cache'),XDG_DATA_HOME=str(session/'xdg-data'),
                       MATCHLAB_REUSE='1',MATCHLAB_ALTERNATE='1' if body.get('alternate',False) else '0')
            if body.get('snapshots',True):env['MATCHLAB_SNAPSHOTS']='1'
            else:env.pop('MATCHLAB_SNAPSHOTS',None)
            if stop_path is not None:env['MATCHLAB_STOP_FILE']=str(Path(stop_path).resolve())
            else:env.pop('MATCHLAB_STOP_FILE',None)
            for i in range(count):
                run_dir=m.ROOT/'runtime/runs'/uuid.uuid4().hex;run_dir.mkdir(parents=True)
                audit_dir=run_dir/'audit';audit_dir.mkdir()
                for path in (session/'audit').iterdir():
                    if path.is_file():(audit_dir/path.name).write_bytes(path.read_bytes())
                child={'schema':1,'engine_pin':m.PIN,'engine_version':'2.0.15-SNAPSHOT','seed':seed+i,
                       'seats':expected_seats(body,i),'opponent':'seat-b','ai_profiles':['Default','Default'],
                       'status':'queued','winner':None,'preboard':True,'run_directory':str(run_dir),
                       'decks':copy.deepcopy(report['decks']),'jar_sha256':jar_hash,'java_version':java_version,
                       'engine_worktree_diff_sha256':diff_hash,'command':command,
                       'reuse_session':str(session),'native_game_number':i+1,'process_mode':'reuse-independent',
                       'seed_policy':series['seed_policy'],'snapshot_schema':1 if body.get('snapshots',True) else None,
                       'normalization':'v1 raw retains native game numbering; result parser maps only result header to Game 1'}
                children.append(child);m.write_json(run_dir/'summary.json',child)
            series.update(status='running',command=command,jar_sha256=jar_hash)
            m.write_json(session/'summary.json',series)
            proc=subprocess.Popen(command,cwd=assets,env=env,stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,start_new_session=True)
            process_started=time.monotonic();idle_started=process_started
            active=None;active_file=None;active_started=None;size=0;next_game=0;pending=b'';failure=None;stopped=False
            startup=(session/'startup.log').open('wb')
            footer=(session/'footer.log').open('wb')
            cleanup.callback(startup.close);cleanup.callback(footer.close)
            def finalize(child,status=None):
                nonlocal active_file
                if active_file:active_file.flush();active_file.close();active_file=None
                raw=Path(child['run_directory'])/'raw.log';data=raw.read_bytes();log=data.decode(errors='replace')
                child.update(raw_bytes=len(data),raw_sha256=m.sha(data),normalized_log_sha256=m.normalized_hash(log),
                             elapsed_seconds=time.monotonic()-active_started)
                errors=[l for l in log.splitlines() if l.startswith('MATCHLAB_SNAPSHOT_ERROR')]
                child['viewer_status']='error' if errors else ('recorded' if 'MATCHLAB_SNAPSHOT ' in log else 'unavailable')
                if errors:child['viewer_errors']=errors
                parsed=re.sub(r'(?m)^Game Result: Game '+str(child['native_game_number'])+r'\b','Game Result: Game 1',log)
                child.update({'status':status,'winner':None} if status else m.parse_result(parsed,0,child['seats']))
                m.write_json(Path(child['run_directory'])/'summary.json',child)
                series['games'].append(copy.deepcopy(child))
                m.write_json(session/'summary.json',series)
                if on_game:on_game(copy.deepcopy(child))
            def consume(line):
                nonlocal active,active_file,active_started,size,next_game,stopped,idle_started
                text=line.decode(errors='replace').rstrip('\r\n')
                begin=marker(text,'MATCHLAB_GAME_BEGIN ')
                if begin is not None:
                    if active is not None or next_game>=count:raise ValueError('Unexpected duplicate native game begin')
                    expected=children[next_game]
                    if begin.get('game')!=next_game+1 or begin.get('seed')!=expected['seed'] or begin.get('decks')!=[s+'.dck' for s in expected['seats']]:
                        raise ValueError('Native game identity/seed/seat mismatch')
                    active=expected;active_started=time.monotonic();size=0
                    if next_game==0:series['startup_seconds']=active_started-process_started
                    active_file=(Path(active['run_directory'])/'raw.log').open('wb')
                    active['status']='running';m.write_json(Path(active['run_directory'])/'summary.json',active)
                if active is not None:
                    if size+len(line)>LIMIT:raise OverflowError('Per-game raw log limit')
                    active_file.write(line);active_file.flush();size+=len(line)
                elif next_game==0:
                    if startup.tell()+len(line)>LIMIT:raise OverflowError('Startup raw log limit')
                    startup.write(line);startup.flush()
                else:
                    if footer.tell()+len(line)>LIMIT:raise OverflowError('Footer raw log limit')
                    footer.write(line)
                end=marker(text,'MATCHLAB_GAME_END ')
                if end is not None:
                    if active is None or end.get('game')!=next_game+1 or end.get('seed')!=active['seed']:
                        raise ValueError('Native game end identity mismatch')
                    healthy=end.get('healthy') is True
                    finalize(active,None if healthy else 'error')
                    active=None;next_game+=1;idle_started=time.monotonic()
                    if not healthy:raise ValueError('Native game failed; reuse aborted')
                if marker(text,'MATCHLAB_SERIES_STOPPED ') is not None:stopped=True
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(proc.stdout,selectors.EVENT_READ)
                    while selector.get_map():
                        now=time.monotonic()
                        if now-(active_started if active is not None else idle_started)>GAME_TIMEOUT:
                            failure='timeout';break
                        for key,_ in selector.select(.05):
                            chunk=os.read(key.fd,65536)
                            if not chunk:selector.unregister(key.fileobj);continue
                            pending+=chunk
                            while b'\n' in pending:
                                line,pending=pending.split(b'\n',1);consume(line+b'\n')
                            if len(pending)>LIMIT:raise OverflowError('Unterminated raw line exceeds limit')
                    if pending:consume(pending)
                    if not failure:
                        try:proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:failure='timeout'
            except OverflowError as exc:
                failure='log_limit';series['error']=str(exc)
            except (OSError,ValueError,json.JSONDecodeError) as exc:
                failure='error';series['error']=str(exc)
            finally:
                if proc.poll() is None or failure:
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                proc.wait();proc.stdout.close()
                if active is not None:finalize(active,failure or 'error')
            series.update(exit_code=proc.returncode,process_seconds=time.monotonic()-process_started)
            if failure:series['status']=failure
            elif stopped:series['status']='stopped'
            elif proc.returncode!=0 or next_game!=count:series['status']='error';series['error']='Native process ended before completing every requested game'
            else:series['status']='completed' if all(g['status'] in ('completed','draw') for g in series['games']) else 'error'
            for child in children:
                if child['status']=='queued':
                    child.update(status='skipped',error='Requested stop' if stopped else 'Session aborted before this game')
                    m.write_json(Path(child['run_directory'])/'summary.json',child)
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        series.update(status='error',error=str(exc))
    finally:
        series['elapsed_seconds']=time.monotonic()-started
        m.write_json(session/'summary.json',series)
    return series

if __name__=='__main__':
    import sys
    try:
        text=sys.stdin.read(1024*1024+1)
        if len(text)>1024*1024:raise ValueError('JSON request exceeds 1 MiB')
        result=run_series(json.loads(text))
        print(json.dumps(result,indent=2))
        raise SystemExit(0 if result['status']=='completed' else 1)
    except (ValueError,OSError) as exc:
        print(json.dumps({'status':'error','error':str(exc)}))
        raise SystemExit(1)

