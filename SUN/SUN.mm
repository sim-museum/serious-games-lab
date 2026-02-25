<map version="freeplane 1.7.0">
<!--To view this file, download free mind mapping software Freeplane from http://freeplane.sourceforge.net -->
<node TEXT="FRI" FOLDED="false" ID="ID_164885352" CREATED="1699841136409" MODIFIED="1699843198050" STYLE="oval">
<font SIZE="18"/>
<hook NAME="MapStyle">
    <properties edgeColorConfiguration="#808080ff,#ff0000ff,#0000ffff,#00ff00ff,#ff00ffff,#00ffffff,#7c0000ff,#00007cff,#007c00ff,#7c007cff,#007c7cff,#7c7c00ff" fit_to_viewport="false"/>

<map_styles>
<stylenode LOCALIZED_TEXT="styles.root_node" STYLE="oval" UNIFORM_SHAPE="true" VGAP_QUANTITY="24.0 pt">
<font SIZE="24"/>
<stylenode LOCALIZED_TEXT="styles.predefined" POSITION="right" STYLE="bubble">
<stylenode LOCALIZED_TEXT="default" ICON_SIZE="12.0 pt" COLOR="#000000" STYLE="fork">
<font NAME="SansSerif" SIZE="10" BOLD="false" ITALIC="false"/>
</stylenode>
<stylenode LOCALIZED_TEXT="defaultstyle.details"/>
<stylenode LOCALIZED_TEXT="defaultstyle.attributes">
<font SIZE="9"/>
</stylenode>
<stylenode LOCALIZED_TEXT="defaultstyle.note" COLOR="#000000" BACKGROUND_COLOR="#ffffff" TEXT_ALIGN="LEFT"/>
<stylenode LOCALIZED_TEXT="defaultstyle.floating">
<edge STYLE="hide_edge"/>
<cloud COLOR="#f0f0f0" SHAPE="ROUND_RECT"/>
</stylenode>
</stylenode>
<stylenode LOCALIZED_TEXT="styles.user-defined" POSITION="right" STYLE="bubble">
<stylenode LOCALIZED_TEXT="styles.topic" COLOR="#18898b" STYLE="fork">
<font NAME="Liberation Sans" SIZE="10" BOLD="true"/>
</stylenode>
<stylenode LOCALIZED_TEXT="styles.subtopic" COLOR="#cc3300" STYLE="fork">
<font NAME="Liberation Sans" SIZE="10" BOLD="true"/>
</stylenode>
<stylenode LOCALIZED_TEXT="styles.subsubtopic" COLOR="#669900">
<font NAME="Liberation Sans" SIZE="10" BOLD="true"/>
</stylenode>
<stylenode LOCALIZED_TEXT="styles.important">
<icon BUILTIN="yes"/>
</stylenode>
</stylenode>
<stylenode LOCALIZED_TEXT="styles.AutomaticLayout" POSITION="right" STYLE="bubble">
<stylenode LOCALIZED_TEXT="AutomaticLayout.level.root" COLOR="#000000" STYLE="oval" SHAPE_HORIZONTAL_MARGIN="10.0 pt" SHAPE_VERTICAL_MARGIN="10.0 pt">
<font SIZE="18"/>
</stylenode>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,1" COLOR="#0033ff">
<font SIZE="16"/>
</stylenode>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,2" COLOR="#00b439">
<font SIZE="14"/>
</stylenode>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,3" COLOR="#990000">
<font SIZE="12"/>
</stylenode>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,4" COLOR="#111111">
<font SIZE="10"/>
</stylenode>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,5"/>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,6"/>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,7"/>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,8"/>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,9"/>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,10"/>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,11"/>
</stylenode>
</stylenode>
</map_styles>
</hook>
<hook NAME="AutomaticEdgeColor" COUNTER="1" RULE="ON_BRANCH_CREATION"/>
<richcontent TYPE="DETAILS">

<html>
  <head>
    
  </head>
  <body>
    <p>
      For a detailed tutorial, chose training
    </p>
    <p>
      in ./q5Go.sh in the ese/FRI directory,
    </p>
    <p>
      choice 2 on the FRI menu
    </p>
  </body>
</html>
</richcontent>
<node TEXT="definitions" FOLDED="true" POSITION="right" ID="ID_146176369" CREATED="1699841181839" MODIFIED="1699841190859">
<edge COLOR="#ff0000"/>
<node TEXT="liberties" FOLDED="true" ID="ID_237562350" CREATED="1699841201023" MODIFIED="1699841208863">
<node TEXT="empty spaces North/South/East/West of a stone" ID="ID_577317319" CREATED="1699841237686" MODIFIED="1699841265926"/>
</node>
<node TEXT="atari" FOLDED="true" ID="ID_1146360643" CREATED="1699841276908" MODIFIED="1699841280982">
<node TEXT="a stone with only one remaining liberty" ID="ID_1121081342" CREATED="1699841281007" MODIFIED="1699841291952"/>
</node>
<node TEXT="double atari" FOLDED="true" ID="ID_284372021" CREATED="1699842200291" MODIFIED="1699842206116">
<node TEXT="two atari threats at the&#xa;same time - difficult&#xa;situation for defender" ID="ID_1208442479" CREATED="1699842206125" MODIFIED="1699842242105"/>
</node>
<node TEXT="ladder" FOLDED="true" ID="ID_571967637" CREATED="1699841325291" MODIFIED="1699841335523">
<node TEXT="zigzag pattern of stone placement&#xa;to prevent encirclement" ID="ID_285302757" CREATED="1699841335545" MODIFIED="1699841369679"/>
</node>
<node TEXT="ladder breaker" FOLDED="true" ID="ID_385401936" CREATED="1699841957823" MODIFIED="1699841962682">
<node TEXT="a stone in the path&#xa;of a ladder which&#xa;blocks the ladder" ID="ID_1018785836" CREATED="1699841962707" MODIFIED="1699842056664"/>
</node>
<node TEXT="ko" FOLDED="true" ID="ID_410259549" CREATED="1699841389523" MODIFIED="1699841392013">
<node TEXT="a capture/recapture infinite loop&#xa;is forbidden, so cannot recapture&#xa;on next move" ID="ID_881253453" CREATED="1699841392043" MODIFIED="1699841444262"/>
</node>
<node TEXT="komi" FOLDED="true" ID="ID_1378931458" CREATED="1699841463482" MODIFIED="1699841467129">
<node TEXT="bonus for going second" ID="ID_260331204" CREATED="1699841467152" MODIFIED="1699841475445"/>
</node>
<node TEXT="alive" FOLDED="true" ID="ID_163818281" CREATED="1699841501973" MODIFIED="1699841505296">
<node TEXT="a group of stones&#xa;that are safe from capture" ID="ID_73440677" CREATED="1699841505323" MODIFIED="1699841515409"/>
</node>
<node TEXT="vital point" FOLDED="true" ID="ID_763465152" CREATED="1699841531283" MODIFIED="1699841538509">
<node TEXT="if defender plays here,&#xa;group is alive.  If the&#xa;player trying to capture&#xa;plays at this point, defenders&#xa;group is dead (will inevitably&#xa;be captured)" ID="ID_1425025850" CREATED="1699841538537" MODIFIED="1699841607095"/>
</node>
<node TEXT="eyes" FOLDED="true" ID="ID_698072963" CREATED="1699841619240" MODIFIED="1699841623444">
<node TEXT="internal points in a group.&#xa;normally, two eyes are needed&#xa;for a group to be alive, but&#xa;there are exceptions" ID="ID_1574838846" CREATED="1699841623450" MODIFIED="1699841662500"/>
</node>
<node TEXT="false eyes" FOLDED="true" ID="ID_1752625847" CREATED="1699841682778" MODIFIED="1699841689654">
<node TEXT="at the tail of a group,&#xa;can be captured" ID="ID_849277913" CREATED="1699841689687" MODIFIED="1699841701163"/>
</node>
<node TEXT="miai" FOLDED="true" ID="ID_404620133" CREATED="1699841714963" MODIFIED="1699841718861">
<node TEXT="having two equivalent options" ID="ID_283650096" CREATED="1699841718894" MODIFIED="1699841724541"/>
</node>
<node TEXT="seki" FOLDED="true" ID="ID_837369430" CREATED="1699841738966" MODIFIED="1699841743625">
<node TEXT="neither player&apos;s group has two eyes,&#xa;yet neither group can be captured" ID="ID_151871831" CREATED="1699841743652" MODIFIED="1699841767573"/>
</node>
<node TEXT="bulky five" FOLDED="true" ID="ID_1011771723" CREATED="1699841784726" MODIFIED="1699841790316">
<node TEXT="an unsettled shape, can be&#xa;killed by playing on the vital point" ID="ID_572129288" CREATED="1699841790340" MODIFIED="1699841808061"/>
</node>
<node TEXT="square-four" FOLDED="true" ID="ID_126532119" CREATED="1699841822126" MODIFIED="1699841829309">
<node TEXT="a square-four shape is an example&#xa;of a dead shape" ID="ID_221722095" CREATED="1699841829331" MODIFIED="1699841861920"/>
</node>
<node TEXT="capturing race" FOLDED="true" ID="ID_629349471" CREATED="1699841890393" MODIFIED="1699841896951">
<node TEXT="when two groups that&#xa;are not independently&#xa;alive try to capture&#xa;each other&#xa;also called a&#xa;semeai" ID="ID_130985165" CREATED="1699841896974" MODIFIED="1699842705173"/>
</node>
<node TEXT="throw-in" FOLDED="true" ID="ID_1581498648" CREATED="1699842083217" MODIFIED="1699842089439">
<node TEXT="placing a stone, with&#xa;the intention that that&#xa;stone is captured immediately&#xa;but this sacrifice leads to a&#xa;net gain" ID="ID_1367683798" CREATED="1699842089468" MODIFIED="1699842134676"/>
</node>
<node TEXT="snapback" FOLDED="true" ID="ID_1839720668" CREATED="1699842150162" MODIFIED="1699842154914">
<node TEXT="capture and immediate&#xa;recapture" ID="ID_834743556" CREATED="1699842154947" MODIFIED="1699842183236"/>
</node>
<node TEXT="empty triangle" FOLDED="true" ID="ID_1922463903" CREATED="1699842282408" MODIFIED="1699842287768">
<node TEXT="an example of a bad shape" ID="ID_206264765" CREATED="1699842287797" MODIFIED="1699842292998"/>
</node>
<node TEXT="knight&apos;s move" FOLDED="true" ID="ID_1091121750" CREATED="1699842314648" MODIFIED="1699842322703">
<node TEXT="tenuous connection&#xa;between stones" ID="ID_1337721827" CREATED="1699842322726" MODIFIED="1699842338830"/>
</node>
<node TEXT="cut" FOLDED="true" ID="ID_463652390" CREATED="1699842349598" MODIFIED="1699842352780">
<node TEXT="a stone placed so as to&#xa;break the connection&#xa;between opponents&apos;&#xa;stones" ID="ID_283830480" CREATED="1699842352803" MODIFIED="1699842376001"/>
</node>
<node TEXT="bamboo joint" FOLDED="true" ID="ID_1751200405" CREATED="1699842391163" MODIFIED="1699842400633">
<node TEXT="a sandwich shape,&#xa;with two empty points&#xa;in the middle" ID="ID_1796024427" CREATED="1699842400661" MODIFIED="1699842420790"/>
</node>
<node TEXT="on space jump" FOLDED="true" ID="ID_1351897335" CREATED="1699842435746" MODIFIED="1699842441336">
<node TEXT="stones separated&#xa;horizontally or&#xa;vertically by one space" ID="ID_676960102" CREATED="1699842441361" MODIFIED="1699842465509"/>
</node>
<node TEXT="tesuji" FOLDED="true" ID="ID_451820846" CREATED="1699842505026" MODIFIED="1699842510409">
<node TEXT="a tactically astute move" ID="ID_643035115" CREATED="1699842510437" MODIFIED="1699842516439"/>
</node>
<node TEXT="tiger&apos;s mouth" FOLDED="true" ID="ID_1580611670" CREATED="1699842531691" MODIFIED="1699842536844">
<node TEXT="empty point shape surrounded&#xa;on 3 sides" ID="ID_796707751" CREATED="1699842536874" MODIFIED="1699842570568"/>
</node>
<node TEXT="peep" FOLDED="true" ID="ID_1295569646" CREATED="1699842587457" MODIFIED="1699842590891">
<node TEXT="stone placed such as&#xa;to threaten to cut&#xa;on the next move" ID="ID_1269649092" CREATED="1699842590919" MODIFIED="1699842609378"/>
</node>
<node TEXT="net" FOLDED="true" ID="ID_576499830" CREATED="1699842645500" MODIFIED="1699842649830">
<node TEXT="diagonal encircling move&#xa;also called a geta" ID="ID_1630799843" CREATED="1699842649858" MODIFIED="1699842663068"/>
</node>
<node TEXT="hane" FOLDED="true" ID="ID_208215076" CREATED="1699842745049" MODIFIED="1699842749435">
<node TEXT="a stone placed&#xa;to bend around a group" ID="ID_607299364" CREATED="1699842749463" MODIFIED="1699842768489"/>
</node>
<node TEXT="6 die 8 live" FOLDED="true" ID="ID_185991770" CREATED="1699842790882" MODIFIED="1699842797280">
<node TEXT="true of a line of stones&#xa;one point away from a&#xa;side of the board" ID="ID_1533683659" CREATED="1699842797307" MODIFIED="1699842842920"/>
</node>
<node TEXT="joseki" FOLDED="true" ID="ID_1993731001" CREATED="1699842871250" MODIFIED="1699842877640">
<node TEXT="a standard opening sequence" ID="ID_1639885538" CREATED="1699842877667" MODIFIED="1699842892574"/>
</node>
<node TEXT="name of the game" FOLDED="true" ID="ID_1521128632" CREATED="1699842950001" MODIFIED="1699842957159">
<node TEXT="Go in Japan&#xa;Baduk in Korea&#xa;Weiqi in China" ID="ID_1198273700" CREATED="1699842957182" MODIFIED="1699842970599"/>
</node>
<node TEXT="higher and lower" FOLDED="true" ID="ID_1562458086" CREATED="1699842985571" MODIFIED="1699842992096">
<node TEXT="respectively, further from&#xa;and closer to an edge of the&#xa;board" ID="ID_1821682500" CREATED="1699842992125" MODIFIED="1699843008321"/>
</node>
</node>
</node>
</map>
