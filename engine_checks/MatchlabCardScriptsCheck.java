import forge.game.ability.*;
import forge.game.card.*;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;

/** Bounded native Forge scenarios, not game/matchup evidence. */
public class MatchlabCardScriptsCheck extends MatchlabRulesCheck {
    static Card enter(String name) {
        Card c=MatchlabRulesCheck.enter(name,me); settle(); drain(game); return c;
    }
    static Card jaceToken() {
        for(Card c:me.getCardsIn(ZoneType.Battlefield))
            if(c.isToken() && c.isPlaneswalker() && c.getType().hasSubtype("Jace")) return c;
        throw new AssertionError("No Jace planeswalker token");
    }
    static int jaceTokens() {
        int n=0;for(Card c:me.getCardsIn(ZoneType.Battlefield))
            if(c.isToken() && c.isPlaneswalker() && c.getType().hasSubtype("Jace")) n++;
        return n;
    }
    static void empower() {
        setup(); Card mentor=enter("Way of the Mentor"); Card token=jaceToken();
        check(token.getCounters(CounterEnumType.LOYALTY)==5,"Mentor enters creates Jace with five loyalty");
        check(token.getColor().hasBlue() && !token.getType().isLegendary(),"Empowered Jace is blue and nonlegendary");
        check(token.getSpellAbilities().stream().anyMatch(sa->sa.getApi()==ApiType.Surveil && sa.hasParam("Planeswalker")),"Jace has native surveil loyalty ability");
        check(token.getSpellAbilities().stream().anyMatch(sa->sa.getApi()==ApiType.Draw && sa.hasParam("Planeswalker")),"Jace has native draw loyalty ability");
        enter("Way of the Paradox");
        check(jaceTokens()==1 && token.getCounters(CounterEnumType.LOYALTY)==10,"Second empower reuses existing Jace token");
        setup(); Card natural=add("Jace, the Mind Sculptor",me); settle();
        enter("Way of the Mentor");
        check(jaceTokens()==1 && natural.getCounters(CounterEnumType.LOYALTY)==0,"Nontoken Jace ignored by empower");
        setup(); Card talent=add("Innkeeper's Talent",me); settle(); levelTalent(talent);
        enter("Way of the Mentor");
        check(jaceToken().getCounters(CounterEnumType.LOYALTY)==10,"Level-three Talent doubles actual empower loyalty placement");
    }
    static void mentorLifeEvents() {
        setup(); enter("Way of the Mentor"); Card token=jaceToken();
        Card ajani=add("Ajani Unrelenting",me); Card enemy=add("Ajani Unrelenting",opp); settle();
        me.gainLife(3,token,null); drain(game);
        check(token.getCounters(CounterEnumType.LOYALTY)==6 && ajani.getCounters(CounterEnumType.LOYALTY)==1,"Mentor adds one loyalty per life-gain event to each own planeswalker");
        check(enemy.getCounters(CounterEnumType.LOYALTY)==0,"Mentor excludes opposing planeswalker");
        me.gainLife(1,token,null); drain(game);
        check(token.getCounters(CounterEnumType.LOYALTY)==7,"Separate life-gain event triggers separately");
    }
    static void paradoxAllowances() {
        setup(); Card paradox=enter("Way of the Paradox"); Card token=jaceToken();
        check(me.getMaxLandPlays()==1,"Paradox grants no land allowance before activation");
        SpellAbility loyalty=ability(token,sa->sa.getApi()==ApiType.Surveil);
        loyalty.setActivatingPlayer(me);
        game.getStack().add(loyalty); drain(game); settle();
        check(me.getLife()==21 && me.getMaxLandPlays()==2,"Paradox loyalty activation gains life and grants one land play");
        game.getStack().add(loyalty); drain(game); settle();
        check(me.getLife()==22 && me.getMaxLandPlays()==3,"Separate loyalty activation stacks land allowance");
        game.getAction().moveToGraveyard(paradox,null); settle();
        check(me.getMaxLandPlays()==3,"Resolved allowance survives Paradox leaving battlefield");
        game.getEndOfTurn().executeUntil(); settle();
        check(me.getMaxLandPlays()==1,"Paradox land allowance expires at end of turn");
    }
    static void shaper() {
        setup(); int lands=me.getCardsIn(ZoneType.Battlefield).size();
        Card c=enter("Simulacrum Shaper");
        Card land=null;for(Card card:me.getCardsIn(ZoneType.Battlefield))if(card.isLand())land=card;
        check(land!=null && land.isTapped() && land.getType().isBasic(),"Shaper ETB searches actual basic onto battlefield tapped");
        int hand=me.getCardsIn(ZoneType.Hand).size();
        SpellAbility kill=AbilityFactory.getAbility("DB$ ChangeZone | Defined$ Self | Origin$ Battlefield | Destination$ Graveyard",c);
        resolve(kill); drain(game);
        check(me.getCardsIn(ZoneType.Hand).size()==hand+1,"Shaper actual death trigger draws exactly one card");
        check(c.getTriggers().stream().filter(t->t.getParam("Destination").equals("Graveyard")).noneMatch(t->t.hasParam("OptionalDecider")),"Shaper death draw is mandatory");
    }
    static void combinedEngineLine() {
        setup(); Card talent=add("Innkeeper's Talent",me); settle(); levelTalent(talent);
        enter("Way of the Mentor"); enter("Way of the Paradox"); Card jace=jaceToken();
        Card ajani=enter("Ajani Unrelenting"); Card corn=add("Ancient Cornucopia",me); settle();
        check(jace.getCounters(CounterEnumType.LOYALTY)==20 && ajani.getCounters(CounterEnumType.LOYALTY)==10,"Combined fixture has real doubled loyalty entry values");
        SpellAbility plus=ability(ajani,sa->sa.getApi()==ApiType.PumpAll); plus.setActivatingPlayer(me);
        for(forge.game.cost.CostPart part:plus.getPayCosts().getCostParts())
            if(part instanceof forge.game.cost.CostPutCounter)
                part.payAsDecided(me,forge.game.cost.PaymentDecision.card(ajani),plus,false);
        check(ajani.getCounters(CounterEnumType.LOYALTY)==12,"Talent doubles actual positive loyalty activation cost");
        game.getStack().add(plus); drain(game); settle();
        check(me.getLife()==21 && me.getMaxLandPlays()==2,"Combined activation resolves Paradox life and land allowance");
        check(ajani.getCounters(CounterEnumType.LOYALTY)==14 && jace.getCounters(CounterEnumType.LOYALTY)==22,"Paradox life triggers Mentor with Talent doubling each own walker counter");
        Card cadet=null;for(Card card:me.getCardsIn(ZoneType.Battlefield))if(card.getName().equals("Cadet"))cadet=card;
        check(cadet!=null && cadet.getNetPower()==3 && cadet.hasKeyword(forge.game.keyword.Keyword.HASTE),"Combined loyalty trigger creates Cadet before Ajani pump resolves");
        Card spell=add("Gruul Spellbreaker",me,ZoneType.Hand);SpellAbility cast=spell.getFirstSpellAbility();cast.setActivatingPlayer(me);
        game.getStack().add(cast);drain(game);settle();
        check(me.getLife()==23,"Cornucopia gains actual two-color spell life in combined board");
        check(ajani.getCounters(CounterEnumType.LOYALTY)==16 && jace.getCounters(CounterEnumType.LOYALTY)==24,"Cornucopia single life event adds one doubled Mentor counter per walker");
    }
    static void ferocity() {
        setup(); Card bear=add("Runeclaw Bear",me); Card aura=add("Ferocity of the Hunt",me,ZoneType.Hand);
        check(aura.getManaCost().getCMC()==2 && aura.getManaCost().toString().contains("{B/G}"),"Ferocity costs actual hybrid {1}{B/G}");
        check(aura.hasKeyword(forge.game.keyword.Keyword.FLASH),"Ferocity has flash");
        Card live=add("Ferocity of the Hunt",me); live.attachToEntity(bear,null); settle();
        check(bear.getNetPower()==3 && bear.getNetToughness()==2 && bear.hasKeyword(forge.game.keyword.Keyword.DEATHTOUCH),"Ferocity grants +1/+0 and deathtouch");
        resolve(AbilityFactory.getAbility("DB$ Destroy | Defined$ Self",bear)); drain(game); settle();
        Card back=null;for(Card c:me.getCardsIn(ZoneType.Battlefield))if(c.getName().equals("Runeclaw Bear"))back=c;
        check(back!=null && back.isTapped(),"Ferocity returns the dead creature to the battlefield tapped");
    }
    static void grapple() {
        setup(); Card mine=add("Runeclaw Bear",me); Card angel=add("Serra Angel",opp); Card green=add("Grizzly Bears",opp);
        Card spell=add("Flourishing Grapple",me,ZoneType.Hand); settle();
        SpellAbility sa=spell.getFirstSpellAbility(); sa.setActivatingPlayer(me);
        check(sa.canTarget(angel) && !sa.canTarget(green) && !sa.canTarget(mine),"Grapple first target is only an opposing red or white permanent");
        sa.getTargets().add(angel); sa.getSubAbility().getTargets().add(mine);
        // A real cast remembers targets on the stack (MagicStack -> handleRemembering) before resolving.
        AbilityUtils.handleRemembering(sa); resolve(sa); drain(game); settle();
        check(!angel.hasKeyword(forge.game.keyword.Keyword.FLYING) && !angel.hasKeyword(forge.game.keyword.Keyword.VIGILANCE),"Grapple target loses all abilities");
        check(angel.getDamage()==2,"Grapple deals damage equal to own creature power");
    }
    public static void main(String[] args) {
        initialize(); empower(); mentorLifeEvents(); paradoxAllowances(); shaper(); combinedEngineLine(); ferocity(); grapple();
        System.out.println("CARD_RULE_SUITE_OK assertions="+assertions);
    }
}
