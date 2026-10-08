import java.util.*;
import java.util.function.Predicate;
import forge.GuiDesktop;
import forge.StaticData;
import forge.ai.LobbyPlayerAi;
import forge.deck.Deck;
import forge.game.*;
import forge.game.ability.*;
import forge.game.card.*;
import forge.game.cost.*;
import forge.game.phase.PhaseType;
import forge.game.player.*;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.game.keyword.Keyword;
import forge.gui.GuiBase;
import forge.item.IPaperCard;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;

/** Native rules checks with explicit fixtures; not a goldfish or matchup simulator. */
public class MatchlabRulesCheck {
    protected static Game game;
    protected static Player me, opp;
    protected static int assertions;
    public static void initialize() {
        GuiBase.setInterface(new GuiDesktop());
        FModel.initialize(null, prefs -> {
            prefs.setPref(FPref.LOAD_CARD_SCRIPTS_LAZILY, false);
            prefs.setPref(FPref.UI_LANGUAGE, "en-US"); return null;
        });
    }
    protected static Game setup() {
        List<RegisteredPlayer> players = new ArrayList<>();
        players.add(new RegisteredPlayer(new Deck()).setPlayer(new LobbyPlayerAi("Fixture A", null)));
        players.add(new RegisteredPlayer(new Deck()).setPlayer(new LobbyPlayerAi("Fixture B", null)));
        GameRules rules = new GameRules(GameType.Constructed);
        game = new Game(players, rules, new Match(rules, players, "Rules fixture"));
        game.setAge(GameStage.Play); game.setNoGUIUser();
        me = game.getPlayers().get(0); opp = game.getPlayers().get(1);
        me.setLife(20, null); opp.setLife(20, null);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, me);
        game.getPhaseHandler().onStackResolved();
        for (int i=0;i<40;i++) { add("Forest", me, ZoneType.Library); add("Forest", opp, ZoneType.Library); }
        return game;
    }
    protected static Card add(String name, Player player, ZoneType zone) {
        IPaperCard paper = FModel.getMagicDb().getCommonCards().getCard(name);
        if (paper == null) { StaticData.instance().attemptToLoadCard(name); paper = FModel.getMagicDb().getCommonCards().getCard(name); }
        if (paper == null) throw new AssertionError("Missing native card: " + name);
        Card card = Card.fromPaperCard(paper, player);
        card.setGameTimestamp(game.getNextTimestamp()); player.getZone(zone).add(card);
        return card;
    }
    protected static Card add(String name, Player player) { return add(name, player, ZoneType.Battlefield); }
    protected static void settle() { game.getAction().checkStaticAbilities(); game.getTriggerHandler().resetActiveTriggers(); }
    protected static SpellAbility ability(Card host, Predicate<SpellAbility> match) {
        for (SpellAbility sa : host.getSpellAbilities()) if (match.test(sa)) return sa;
        throw new AssertionError("No matching ability on " + host.getName());
    }
    protected static void resolveAbility(Card host, Predicate<SpellAbility> match) {
        SpellAbility sa=ability(host, match); sa.setActivatingPlayer(host.getController()); AbilityUtils.resolve(sa); settle();
    }
    protected static void resolve(SpellAbility sa) { sa.setActivatingPlayer(sa.getHostCard().getController()); AbilityUtils.resolve(sa); settle(); }
    protected static void drain(Game g) {
        for(int i=0;i<100;i++) {
            g.getTriggerHandler().runWaitingTriggers();
            g.getStack().addAllTriggeredAbilitiesToStack();
            if(g.getStack().isEmpty()) return;
            g.getStack().resolveStack();
        }
        throw new AssertionError("Rules fixture exceeded 100 native resolutions");
    }
    protected static void check(boolean success, String message) {
        assertions++; if(!success) throw new AssertionError(message); System.out.println("RULE_PASS " + message);
    }
    protected static int count(String name, Player p, ZoneType zone) {
        int n=0;for(Card c:p.getCardsIn(zone))if(c.getName().equals(name))n++;return n;
    }
    protected static void levelTalent(Card talent) {
        resolveAbility(talent, sa->sa.getApi()==ApiType.ClassLevelUp && sa.isClassLevelNAbility(talent.getClassLevel()));
        resolveAbility(talent, sa->sa.getApi()==ApiType.ClassLevelUp && sa.isClassLevelNAbility(talent.getClassLevel()));
        check(talent.getClassLevel()==3,"Talent native class upgrade reaches level 3");
    }
    protected static Card enter(String name, Player player) {
        Card c=add(name,player,ZoneType.Hand);
        SpellAbility cause=c.getFirstSpellAbility();cause.setActivatingPlayer(player);
        Map<AbilityKey,Object> params=AbilityKey.newMap();
        CardZoneTable zones=AbilityKey.addCardZoneTableParams(params,cause);
        Card moved=game.getAction().moveToPlay(c,player,cause,params);
        zones.triggerChangesZoneAll(game,cause);
        return moved;
    }
    protected static void talentCountersAndWard() {
        setup();Card talent=add("Innkeeper's Talent",me);settle();levelTalent(talent);
        Card ajani=enter("Ajani Unrelenting",me);settle();
        check(ajani.getCounters(CounterEnumType.LOYALTY)==10,"Talent doubles entering Ajani printed five loyalty to ten");
        Card bear=add("Runeclaw Bear",me);settle();
        GameEntityCounterTable table=new GameEntityCounterTable();
        bear.addCounter(CounterEnumType.P1P1,1,me,table);table.replaceCounterEffect(game,ajani.getFirstSpellAbility());settle();
        check(bear.getCounters(CounterEnumType.P1P1)==2,"Talent doubles own +1/+1 counters");
        check(bear.hasKeyword(Keyword.WARD),"Talent level 2 grants ward to a permanent with counters");
        check(!talent.hasKeyword(Keyword.WARD),"Talent does not grant ward to counter-free permanents");
        table=new GameEntityCounterTable();bear.addCounter(CounterEnumType.P1P1,1,opp,table);table.replaceCounterEffect(game,ajani.getFirstSpellAbility());
        check(bear.getCounters(CounterEnumType.P1P1)==3,"Talent does not double counters placed by an opponent");
    }
    protected static void unrelentingTriggersAndDraw() {
        setup();Card ajani=enter("Ajani Unrelenting",me);settle();
        SpellAbility plus=ability(ajani,sa->sa.getApi()==ApiType.PumpAll);plus.setActivatingPlayer(me);
        // Pay the actual native +1 loyalty cost, then activate through the real stack.
        for(CostPart part:plus.getPayCosts().getCostParts()) if(part instanceof CostPutCounter)part.payAsDecided(me,PaymentDecision.card(ajani),plus,false);
        game.getStack().add(plus);drain(game);
        check(ajani.getCounters(CounterEnumType.LOYALTY)==6,"Unrelenting +1 pays actual loyalty counter cost");
        check(count("Cadet",me,ZoneType.Battlefield)==1,"Own loyalty activation triggers one real Cadet");
        Card cadet=null;for(Card c:me.getCardsIn(ZoneType.Battlefield))if(c.getName().equals("Cadet"))cadet=c;
        check(cadet!=null&&cadet.getNetPower()==3&&cadet.hasKeyword(Keyword.HASTE),"Cadet trigger resolves before +1 pump and gains haste");
        Card theirs=enter("Ajani, Caller of the Pride",opp);settle();
        SpellAbility rival=ability(theirs,sa->sa.getApi()==ApiType.PutCounter);rival.setActivatingPlayer(opp);rival.getTargets().add(cadet);
        game.getStack().add(rival);drain(game);
        check(count("Cadet",me,ZoneType.Battlefield)==1,"Opponent loyalty activation does not trigger Unrelenting");
        add("Plains",me,ZoneType.Hand);add("Island",me,ZoneType.Hand);
        SpellAbility minus=ability(ajani,sa->sa.getApi()==ApiType.Discard);minus.setActivatingPlayer(me);
        game.getStack().add(minus);drain(game);
        check(count("Cadet",me,ZoneType.Battlefield)==2,"Unrelenting -2 creates a Cadet before counting creatures");
        check(me.getCardsIn(ZoneType.Hand).size()==2,"Unrelenting discards hand then draws for both actual creatures");
        check(count("Plains",me,ZoneType.Graveyard)==1&&count("Island",me,ZoneType.Graveyard)==1,"Unrelenting's previous hand is actually discarded");
    }
    protected static void unrelentingDamageTokenExceptions() {
        setup();Card ajani=enter("Ajani Unrelenting",me);
        Card own=add("Runeclaw Bear",me),enemy=add("Runeclaw Bear",opp);
        SpellAbility token=AbilityFactory.getAbility("DB$ Token | TokenScript$ cadet",ajani);token.setActivatingPlayer(me);AbilityUtils.resolve(token);
        token=AbilityFactory.getAbility("DB$ Token | TokenScript$ cadet",enemy);token.setActivatingPlayer(opp);AbilityUtils.resolve(token);settle();
        SpellAbility damage=ability(ajani,sa->sa.getApi()==ApiType.DamageAll);damage.setActivatingPlayer(me);AbilityUtils.resolve(damage);
        check(own.getDamage()==4&&enemy.getDamage()==4,"Unrelenting -3 damages own nontoken and opposing nontoken creatures");
        for(Card c:me.getCardsIn(ZoneType.Battlefield))if(c.getName().equals("Cadet"))check(c.getDamage()==0,"Unrelenting -3 excludes own tokens");
        for(Card c:opp.getCardsIn(ZoneType.Battlefield))if(c.getName().equals("Cadet"))check(c.getDamage()==4,"Unrelenting -3 still damages opposing tokens");
    }
    protected static void cornucopiaCastGate() {
        setup();Card corn=add("Ancient Cornucopia",me);settle();
        Card spell=add("Gruul Spellbreaker",me,ZoneType.Hand);SpellAbility sa=spell.getFirstSpellAbility();sa.setActivatingPlayer(me);game.getStack().add(sa);drain(game);
        check(me.getLife()==22,"Cornucopia gains life for both actual colors of a spell");
        spell=add("Llanowar Elves",me,ZoneType.Hand);sa=spell.getFirstSpellAbility();sa.setActivatingPlayer(me);game.getStack().add(sa);drain(game);
        check(me.getLife()==22,"Cornucopia is limited to one resolved gain each turn");
        spell=add("Llanowar Elves",opp,ZoneType.Hand);sa=spell.getFirstSpellAbility();sa.setActivatingPlayer(opp);game.getStack().add(sa);drain(game);
        check(me.getLife()==22,"Opponent spells do not trigger Cornucopia");
    }
    protected static void mindStoneBlink() {
        setup();Card stone=enter("The Mind Stone",me);Card ajani=enter("Ajani Unrelenting",me);settle();
        check(stone.hasKeyword(Keyword.INDESTRUCTIBLE),"The Mind Stone retains indestructible");
        check(!stone.isHarnessed(),"The Mind Stone starts unharnessed");
        resolveAbility(stone,sa->sa.getApi()==ApiType.AlterAttribute);
        check(stone.isHarnessed(),"Native harness ability enables the infinity trigger");
        ajani.setCounters(CounterEnumType.LOYALTY,1);settle();
        forge.game.trigger.Trigger blink=stone.getTriggers().get(0);SpellAbility ability=blink.ensureAbility();ability.setActivatingPlayer(me);ability.getTargets().add(ajani);AbilityUtils.resolve(ability);settle();
        Card returned=null;for(Card c:me.getCardsIn(ZoneType.Battlefield))if(c.getName().equals("Ajani Unrelenting"))returned=c;
        check(returned!=null&&returned.getCounters(CounterEnumType.LOYALTY)==5,"Mind Stone actually blinks Ajani and restores printed loyalty");
        check(returned!=ajani,"Mind Stone blink produces a new native game object");
    }
    public static void main(String[] args) {
        initialize();
        talentCountersAndWard();unrelentingTriggersAndDraw();unrelentingDamageTokenExceptions();cornucopiaCastGate();mindStoneBlink();
        System.out.println("RULE_SUITE_OK assertions="+assertions);
    }
}
