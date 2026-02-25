GPL 60 fps patch, version 2

June 2009

Petteri Pajunen and Nigel Pattinson


WHAT's NEW

* servers running 60fpsv2 will only accept clients running the same patch
* minor 67 AI changes


IMPORTANT

* original 67 is supported, but apart from AI, mods are expected to work with this patch (see section MODS for important information)
* do not join 36fps servers with this or earlier 60fps patch. Mixing fps does not work, and may cause problems to others on the server
* GEM+ is required for installing the patch (see http://gem.ebi-service.de/)
* Carsound patch (you can use GEM+ to set it) and the corresponding extra sounds are required

System requirements are impossible to specify accurately, as well as unnecessary since it is easy test it yourself (the patch is a small download and easy to install/uninstall). 60 fps is no free lunch, so considerably more PC performance is needed. Test it on your PC, and read the feedback from other users to get a better idea what is required.


INSTALLATION

Put the patch file 60FPSv2.xml in the GEM+ Options folder, located by default at

  C:\Program Files\GPLSecrets\GEM+\Options

Start GEM+ and check the box next to "60fpsv2". Start GPL, which should now be running at 60 fps. Check your fps display to ensure this. For best results, use a display mode with 60 Hz vertical refresh rate and set vsync on. Consider setting your ffb latency to zero, since higher values may give unwanted ffb effects.

GEM+ produces a patched exe called gplc67.exe (other names are used for mods), which you can use to start GPL directly if you prefer to do so. Only patching and unpatching needs to be done through GEM+.


MULTIPLAYER

Hosting a race with the server running 60fpsv2 requires that all clients use the same patch. Anyone trying to join with 36fps or an earlier 60fps patch will receive a message "you are not qualified to drive". Technically it is possible to join a 36fps server while using the 60fpsv2 patch, but it should not be done. Mixing fps online does not work, and may cause problems to others on track.

The following Core.ini parameters are recommended (change them if you know what you are doing):


net_mdm_client_send_every = 5                ; Client packet freq on dialup
net_mdm_client_send_size = 84                ; Client packet size on dialup
net_mdm_server_send_every = 5                 ; Server packet freq on dialup
net_mdm_server_send_size = 384               ; Server packet size on dialup
net_server_port=0                             ; Server port number (0 = default)
net_use_mdm_bandwidth_for_tcp_ip=1            ; Use modem bandwidthfor TCP/IP - 1 = Use net_mdm_ settings *

The reason for using send_every = 5 instead of the commonly used 3 is that networking code is also speeded up. Send_every = 3 means sending data every third frame (12 times per second in original GPL). Using send_every = 5 means sending data every fifth frame, which is again 12 times per second when using the 60 fps patch. Send_size parameters are not affected by the 60 fps patch, so they can be chosen as before.


AI

AI works to some extent with the original 67. 60fps mod AI is not working well, since mod AI is not compatible with 60fps AI in most cases. There is no need for bug reports on 60fps mod AI.

Use either the original gpl_ai.ini, or back it up and replace it with the supplied gpl_ai_60fps.ini (renaming to gpl_ai.ini when using with the original 67).


UTILITIES SUPPORTING 60FPS

* Pribluda
* iGOR
* CCM
* VROC (launch it from GEM+ so gpl.exe will be patched)
* patched GPLRA (does not analyze laps correctly, but generates correct race reports). See http://srmz.net/.
* many others, since most utilities are unaffected by fps


MODS

The patch is expected to work with all mods, apart from the AI. However, newer mods have changed the part of the code which is needed for client/server fps matching. Therefore it is necessary to use a separate version of the 60fpsv2 patch with them. This is inconvenient and potentially confusing, but there is no better solution which can be implemented by me. The patch 60fpsv2newmod.xml should be used with all recently updated mods, and probably with the upcoming 67 mod. NOTE: this patch has been tested very little, and is considered a test version. Please report here if the online fps matching does not work, or if there are other obvious problems.


KNOWN ISSUES

* Online replays have extra jumpiness. This is a general GPL issue, and 60 fps simply makes the problem more obvious. 
* There are frequent 'double-clicks' especially in the setup screen.
* Moving 3do objects (flags etc..) move too fast on some tracks.
* Mixing 36 fps and 60 fps online does not work correctly. This version of the patch implements fps checking, so hosting with 60fpsv2 should avoid the problem. But those servers which are not patched, or are running the 60fpsv1 patch, can be joined with wrong fps. Drivers should find out what fps is used on the server, and use the correct version when joining. 
* a patched GPLRA loads 60fps replays and generates correct race reports, but does not analyze the laps correctly. Please do not report on this, since it is a known issue. Consider using the patched GPLRA for race reports only.


GPL Rank

The 60 fps patch has no effect on storing record laptimes in player.ini. Therefore non-WR record laps made with the 60 fps patch will not be treated differently from 36 fps record laps when uploading to GPL Rank. If you want to keep 60 fps records separate, the easiest solution is to make a separate player for 60 fps.


REPORTING BUGS

First, read the README carefully to check if the issue is known or if there is a known solution. Next, read the release thread since others may have reported the same bug. If its new, post in the release thread with all relevant information. Also, consider which is the most likely cause of the bug. If its a problem with one of the utilities, rasterisers, or the mods, I cannot do anything about it. In that case it is better to post the report somewhere else.


CREDITS

Thanks for testing:

	William Campbell
	Bill Cooper
	dangermouse
	ducwolf
	Aleksi Elomaa
	Phil Flack
	Allie Fraser
	Ginetto
	Stewart Grove
	Juha Hallikainen
	Elias Hirvonen
	Remco Hitman
	Robbie Hunter
	Jackseller
	Barry Kooistra
	Harri Lattu
	MECH
	Ken Murray
	Guillaume Nachin
	Simon Nott
	Tommie van Ostade
	Remy Roesz
	Paul Skingley
	Vosblod
	Phil Woodward
	Stefano Zampedri


	I've lost track of some testers, thanks to all not mentioned here
