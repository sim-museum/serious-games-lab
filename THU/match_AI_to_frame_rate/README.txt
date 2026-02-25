[H[2J[3J------------------------------------------------------------------------------------
How to race against computer controlled (AI) cars with fast (60 frames per second) graphics refresh rate
------------------------------------------------------------------------------------
 Optional: read on if interested in smoother GPL-DEMO graphics at the cost of 
 lower quality driving by the computer controlled (AI) cars...
 Checking the 60 Frames per Second (FPS) option on the lower right in the GPL-DEMO GEM+ screen 
 will make the action noticably smoother on most screens, but it also causes poor AI driving. 
 If playing online without AI, by all means switch to 60 FPS from the default 36 FPS if the 
 computer hosting the game is set to 60 FPS.
 If you want to race against AI drivers at 60 FPS, run the  gpl_ai_60fpsv2newmod.sh script first 
 unless you're using the 67x, 67SC or 69X carset, in which case run the gpl_ai_60fpsaiv1.sh script first. 
 To return to the default 36 FPS for stronger AI driving, run the  gpl_ai_default.sh script before
 deselecting 60 FPS in GEM+.  If satisfied with the slower 36 FPS frame rate, there's no reason 
 to change settings unless joining an online race where the frame rate is 60 FPS.
 
./gpl_ai_default.sh: switch to legacy 36 frames per second (FPS) setting for computer-controlled (AI) cars
     Run this script before turning off GEM+ 60 FPS options gpl_ai_60fpsv2newmod or gpl_ai_60fpsaiv1.sh
     Slowing down the frame rate make animation slightly less smooth, but is sometimes needed for
     compatibility when racing online using iGOR or VROC
 
./gpl_ai_60fpsv2newmod.sh: run before switching to smoother 60 FPS GEM+ option gpl_ai_60fpsv2newmod
 
./gpl_ai_60fpsaiv1.sh.sh: run before switching to smoother 60 FPS GEM+ option gpl_ai_60fpsaiv1

reference:
http://srmz.net/index.php?showtopic=12365
