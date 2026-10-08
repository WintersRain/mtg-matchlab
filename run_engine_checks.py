#!/usr/bin/env python3
"""Compile/run real Forge rules fixtures in a locked, isolated privacy-patched runtime."""
import json,os,subprocess,uuid,fcntl
from pathlib import Path
from contextlib import ExitStack
import matchlab as m

def main():
    root=m.ROOT; runtime=root/'runtime';run_dir=runtime/'rules-checks'/uuid.uuid4().hex;run_dir.mkdir(parents=True)
    java=root/'.local/jdk-17.0.20.1+1/bin/java';javac=java.with_name('javac')
    jar=root/'vendor/forge/forge-gui-desktop/target/forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar'
    sources=sorted((root/'engine_checks').glob('*.java'));classes=run_dir/'classes';classes.mkdir()
    compiled=subprocess.run([str(javac),'-cp',str(jar),'-d',str(classes),*[str(p) for p in sources]],capture_output=True,text=True)
    print(compiled.stdout+compiled.stderr,end='')
    if compiled.returncode:return compiled.returncode
    summary={'jar_sha256':m.sha(jar.read_bytes()),'engine_pin':m.PIN,'sources':{p.name:m.sha(p.read_bytes()) for p in sources},'checks':[]}
    with (runtime/'run.lock').open('w') as lock,ExitStack() as cleanup:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        dirs={k:run_dir/v for k,v in [('userDir','user'),('cacheDir','cache'),('decksDir','decks'),('decksConstructedDir','decks/constructed')]}
        for p in dirs.values():p.mkdir(parents=True,exist_ok=True)
        home=run_dir/'home';home.mkdir()
        profile=root/'vendor/forge/forge-gui/forge.profile.properties';config=run_dir/'forge.profile.properties'
        config.write_text(''.join(f'{k}={v}\n' for k,v in dirs.items()));profile.symlink_to(config);cleanup.callback(profile.unlink)
        env=os.environ.copy();env.update(HOME=str(home),XDG_CONFIG_HOME=str(run_dir/'config'),XDG_CACHE_HOME=str(run_dir/'xdgcache'),XDG_DATA_HOME=str(run_dir/'data'))
        for key in ['JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS','MATCHLAB_SNAPSHOTS']:env.pop(key,None)
        for source in sources:
            name=source.stem;raw=run_dir/(name+'.log')
            command=[str(java),'-Djava.awt.headless=true','-Duser.home='+str(home),'-cp',str(jar)+':'+str(classes),name]
            result=m.capture(command,root/'vendor/forge/forge-gui',env,raw,timeout=120)
            log=raw.read_text(errors='replace');print(log[-9000:],flush=True)
            passed=result['exit_code']==0 and 'RULE_SUITE_OK' in log and not result['status']
            summary['checks'].append({'name':name,'passed':passed,'raw_sha256':m.sha(raw.read_bytes()),**result})
    summary['run_directory']=str(run_dir);m.write_json(run_dir/'summary.json',summary);print(json.dumps(summary,indent=2))
    return 0 if all(x['passed'] for x in summary['checks']) else 1
if __name__=='__main__':raise SystemExit(main())
