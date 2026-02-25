				MiG Alley(tm)

History/Geschichte
------------------
V1.23	Compiled 13 April    2000
V1.22	Compiled 24 Febuary  2000
V1.21	Compiled  8 Febuary  2000
V1.2	Compiled  4 Febuary  2000 
V1.1	Compiled  1 December 1999
V1.03	Compiled 27 August   1999
v1.02	Compiled 19 August   1999
v1.01	Compiled 01 August   1999

The version number is available in two places:
	end of the credits
	right click on \rowan\mig\MIG.EXE and then click on the Version
	tab.
	Applying the patch will invalidate all existing savegames and
	recorded videos.

The following language versions are available in this file:
	English
	Deutsch 
	Français
	Español


--------------------------------------------------------------------------------
CONTENTS   (English)
--------------------------------------------------------------------------------
1	Logitech Force Feedback Stick Settings
2	Keys
3	V1.02 
4	Workarounds
5	V1.03
6	V1.1
7	Multiplayer Views
8	V1.23

--------------------------------------------------------------------------------
1	Logitech Force Feedback Stick Settings

If you are using a "Logitech Wingman Force", it is recommended that the Spring 
Effect Strength on the Settings panel of the Game Controllers dialog box, be set 
to 35%.  This will prevent excessive stick stiffness and uncommanded vibration 
of the joystick.

2	Keys 

The Controls program can be used to reconfigure the keys in MiG Alley. This 
program can be found in the directory in which MiG Alley was installed,


3	V1.02

Fixes:-
	AWE64 Sound FX missing
	Random Crashes in the 3D [Audio triggers]
	Smoke trails going jagged
	Random Crashes in the replay [audio and accel]
	Rcombo Crashes [mainly on the Prefereneces Screen]
	Missing dialogs if Windows Font is 110% or 200%
	Improved font if 'Intel' font not installed
	USB Joysticks cooperating with other USB devices
	Memory leak going from the 3D to the preferences screen
	
4	Workarounds (V1.1)

The following issues affect some users. We will continue to fix these and other 
issues in future patches, meanwhile the workarounds described will improve the
enjoyment of affected users.

Voodoo2 and TNT2 together:
 Either	Select 800x600 or lower resolution (1024x768 is selected by default)
 Or	Disable "Voodoo 2 Direct 3D Support" to get all resolutions on the TNT2
	if the option is listed on Advanced from the Voodoo2 tab of Display 
	Properties.

No 'stencil' style font on the front screens:
	Reinstall the "Intel.ttf" truetype font which is in c:\windows\fonts 

TnT has fuzzy fonts
	Change the number of auto-generated Mip-Map levels to 0 [it
	defaults to 10]

VooDoo2 SLI mode
	If you have a problem then disable SLI support - it is listed on 
	Advanced from the Voodoo2 tab of Display Properties.

Keyboard not responding
	If the keyboard fails to respond when in the 3d then remove any joystick 
	control or profiler programs that are enabled.

Bad in game Fonts
	if you only seem to be able to get Wingdings or some other
	strange font you may need to re-install the font.
	this is called intel.ttf and can be found on the website
	[http://www.cix.co.uk/~rowan/Mig/intel.ttf]
	if this does not help then remove it and the game should choose
	a Times Roman font.

Cannot access the icons on the map toolbar
	switch off the 'Smart Move' feature of your mouse or main
	crontroller.

5	V1.03 [demo build + fixes]
	Software driver - explosions made correct colour
	Fixed Photo Zoom jitter
	Target Diamond works in software driver mode
	Ctrl-5 / enter - new view glance at instruments
	Map work :- [waypoints info, mid-level map, hi-detail map]
	removed troops from inside the hill on CAS UN attacking mission
	Flaps - now have Full up mid and down i.e.
		f 	toggles full on / full off
		shift-f	half on [or half off]
		shift-r	Full on
		shift-v Full off

6	MiG Alley: Version 1.1
	-----------------------
	December 1999
	Stuttering in Multiplayer squashed

	November 1999
	The Sticky key problem has now been fixed

	September 1999

	This note defines the changes to V1.02 of MiG Alley.
	
	Navigation
	----------
	A mid-level zoom has been added to the map. The large-scale map has also 
	been improved.

	On the map screen the bearing and range from your aircraft to the Current 
	waypoint is displayed. For other waypoints, the bearing and range from 
	the previous waypoint is displayed. 
	In the cockpit there is an extra info line of navigational information.

	Controls
	--------
	You can glance at the instruments using either ctrl 5 or Number Pad 
	Enter.
	Mouse panning is now disabled when on the map or on sticky keys.
	A midway flaps option has been added:
		Shift r	flaps up
		Shift f	flaps midway
		Shift v	flaps down
	On most machines, the key to the left of the main keypad "1" key gives 
	zero rpm.  
	
	Graphic Glitches
	----------------
	On the CAS UN Attacking Quick Mission the troops on the hill are 
	now visible.
	The Software Driver explosions no longer use strange colours.
	On Photo zoom, the small judder on max zoom out has been removed.
	With the Software Driver, the red target diamond now follows the target 
	correctly.
	The flying crater bug has been fixed.
	An aircraft's shadow will not be visible when it has been destroyed.
	The clock hour hand moves more realistically.
	The front gear suspension on the F80 now animates realistically.
	The problems with the horizon ball have been fixed

	Game Play Issues
	----------------
	MiGs are more aggressive. You need to hit them harder before they will 
	stand-down.
	The MiGs take-off from the Southern airfields even when Sabres are in 
	the vicinity.
	In the Campaign Armed Reconn missions, vehicles can be seen travelling 
	along roads.
	Armed Reconn and CAS logic has been improved.
	It is now possible to change the targets on preplanned missions.
	Activity in Battle areas has been increased. Barrages are visible.
	On the CAS UN Defending quick mission, the mission can be completed 
	because your pilots will attack and destroy enemy forces.
	The weapons potency has been tuned to make attacks against ground forces 
	more successful.
	On the UN Fighter Bomber Strike 2 quick mission the default target is now 
	Wonju. This target is well protected by AAA. Also your aircraft will now 
	be carrying 1000lb bombs.
	If you are not the leader, you get prompted to start your attack 
	during strike missions.

7	Multiplayer Views

Restricted views.
	Restricted views prevent players from using padlocks or the pan 
	view commands. This is rather draconian and is intended to be so that 
	all players have the same restrictions.

8	MiG Alley Version 1.23
	----------------------
	Graphics
	Target Lock stutter fixed.
		
	Graphics Cards
	TnT+VooDoo2 graphics selection problem fixed. If you had two D3D 
	capable cards in your machine then it was possible to get a D3D error 
	for an illegal mode. For example this occurred when you selected 
	1024x768 for a TnT with a single VooDoo2.
		
	Flight
	F51 Speed Indicator fixed, it is now accurate up to about 500 Knots.
	
	Multiplayer
	
	Match and Team play Internet connections more stable and smooth. 
	Quick missions are improved but not perfect.
	The warping bug that was very noticeable on dial-up connections has 
	been removed.
	Many initialisation problems have been fixed by making the comms 
	packages smaller.
	
	Controls		
	Joysticks can now use the 'Z' Axis as a rudder [this was previously 
	limited to throttles].
	
	Notes
	If you update your graphics hardware with MA installed you must delete
	the savegame\settings.mig file out of the installed directory.

	Don't use EndItAll.exe or a similar program that shuts down tasks 
	if multiplayer games crash [particularly the guests] when entering 
	the 3D.

	For the 'Auto Frame Rate' preference, there is an extra option named 
	"fast". Use this option on fast machines if you suffer from "Ground 
	Stutter".
	
	General Bug Fixes
	Crack and Burn bug fixed.
	Crash when selecting trees as targets fixed.
	Crash when pressing tab/fire/pause on take-off fixed.
	Too many radio messages crash fixed.
	Music / audio thread crash fixed.
	Photo bug which seems to be generated from DX7 fixed.
	Fixed attacking bug in comms.
	Fixed a memory leak in the 3D.
	Fixed bad fuel reporting.


--------------------------------------------------------------------------------
INHALT	(Deutsch)
--------------------------------------------------------------------------------
1	Logitech Force Feedback-Joystick-Einstellungen
2	Tasten
3	V1.02 
4	Workarounds
5	V1.03
6	V1.1
7	Multiplayer Views
8	V1.23

--------------------------------------------------------------------------------
1	Logitech Force Feedback-Joystick-Einstellungen

Wenn Sie einen "Logitech Wingman Force" verwenden, wird empfohlen, im Dialogfeld 
"Spielsteuerungen" in den Einstellungen die Sprungfederstärke auf 35% 
einzustellen. Dadurch wird verhindert, daß der Joystick zu unbeweglich wird und 
ungewollte Vibrationen entstehen. 

2	Tasten

Sie können das Steuerungsprogramm verwenden, um im Installationsverzeichnis von 
MiG Alley die Tasten neu zu konfigurieren. 
 
3	V1.02

Fixes:-
	AWE64 Sound FX missing
	Random Crashes in the 3D [Audio triggers]
	Smoke trails going jagged
	Random Crashes in the replay [audio and accel]
	Rcombo Crashes [mainly on the Prefereneces Screen]
	Missing dialogs if Windows Font is 110% or 200%
	Improved font if 'Intel' font not installed
	USB Joysticks cooperating with other USB devices
	Memory leak going from the 3D to the preferences screen
	
4	Workarounds (V1.1)

The following issues affect some users. We will continue to fix these and other 
issues in future patches, meanwhile the workarounds described will improve the
enjoyment of affected users.

Voodoo2 and TNT2 together:
 Either	Select 800x600 or lower resolution (1024x768 is selected by default)
 Or	Disable "Voodoo 2 Direct 3D Support" to get all resolutions on the TNT2
	if the option is listed on Advanced from the Voodoo2 tab of Display 
	Properties.

No 'stencil' style font on the front screens:
	Reinstall the "Intel.ttf" truetype font which is in c:\windows\fonts 

TnT has fuzzy fonts
	Change the number of auto-generated Mip-Map levels to 0 [it
	defaults to 10]

VooDoo2 SLI mode
	If you have a problem then disable SLI support - it is listed on 
	Advanced from the Voodoo2 tab of Display Properties.

Keyboard not responding
	If the keyboard fails to respond when in the 3d then remove any 
	joystick control or profiler programs that are enabled.

Bad in game Fonts
	if you only seem to be able to get Wingdings or some other
	strange font you may need to re-install the font.
	this is called intel.ttf and can be found on the website
	[http://www.cix.co.uk/~rowan/Mig/intel.ttf]
	if this does not help then remove it and the game should choose
	a Times Roman font.

Cannot access the icons on the map toolbar
	switch off the 'Smart Move' feature of your mouse or main
	crontroller.

5	V1.03 [demo build + fixes]
	Software driver - explosions made correct colour
	Fixed Photo Zoom jitter
	Target Diamond works in software driver mode
	Ctrl-5 / enter - new view glance at instruments
	Map work :- [waypoints info, mid-level map, hi-detail map]
	removed troops from inside the hill on CAS UN attacking mission
	Flaps - now have Full up mid and down i.e.
		f 	toggles full on / full off
		shift-f	half on [or half off]
		shift-r	Full on
		shift-v Full off

6	MiG Alley: Version 1.1
	-----------------------
	November 1999
	The Sticky key problem has now been fixed

	September 1999

	This note defines the changes to V1.02 of MiG Alley.
	
	Navigation
	----------
	A mid-level zoom has been added to the map. The large-scale map has also 
	been improved.

	On the map screen the bearing and range from your aircraft to the Current 
	waypoint is displayed. For other waypoints, the bearing and range from 
	the previous waypoint is displayed. 
	In the cockpit there is an extra info line of navigational information.

	Controls
	--------
	You can glance at the instruments using either ctrl 5 or Number Pad 
	Enter.
	Mouse panning is now disabled when on the map or on sticky keys.
	A midway flaps option has been added:
		Shift r	flaps up
		Shift f	flaps midway
		Shift v	flaps down
	On most machines, the key to the left of the main keypad "1" key gives 
	zero rpm.  
	
	Graphic Glitches
	----------------
	On the CAS UN Attacking Quick Mission the troops on the hill are 
	now visible.
	The Software Driver explosions no longer use strange colours.
	On Photo zoom, the small judder on max zoom out has been removed.
	With the Software Driver, the red target diamond now follows the target 
	correctly.
	The flying crater bug has been fixed.
	An aircraft's shadow will not be visible when it has been destroyed.
	The clock hour hand moves more realistically.
	The front gear suspension on the F80 now animates realistically.
	The problems with the horizon ball have been fixed

	Game Play Issues
	----------------
	MiGs are more aggressive. You need to hit them harder before they will 
	stand-down.
	The MiGs take-off from the Southern airfields even when Sabres are in 
	the vicinity.
	In the Campaign Armed Reconn missions, vehicles can be seen travelling 
	along roads.
	Armed Reconn and CAS logic has been improved.
	It is now possible to change the targets on preplanned missions.
	Activity in Battle areas has been increased. Barrages are visible.
	On the CAS UN Defending quick mission, the mission can be completed 
	because your pilots will attack and destroy enemy forces.
	The weapons potency has been tuned to make attacks against ground forces 
	more successful.
	On the UN Fighter Bomber Strike 2 quick mission the default target is now 
	Wonju. This target is well protected by AAA. Also your aircraft will now 
	be carrying 1000lb bombs.
	If you are not the leader, you get prompted to start your attack 
	during strike missions.


7	Multiplayer Views

Restricted views.
	Restricted views prevent players from using padlocks or the pan 
	view commands. This is rather draconian and is intended to be so that 
	all players have the same restrictions.

8	MiG Alley Version 1.23
	----------------------
	Graphics
	Target Lock stutter fixed.
		
	Graphics Cards
	TnT+VooDoo2 graphics selection problem fixed. If you had two D3D 
	capable cards in your machine then it was possible to get a D3D error 
	for an illegal mode. For example this occurred when you selected 
	1024x768 for a TnT with a single VooDoo2.
		
	Flight
	F51 Speed Indicator fixed, it is now accurate up to about 500 Knots.
	
	Multiplayer
	
	Match and Team play Internet connections more stable and smooth. 
	Quick missions are improved but not perfect.
	The warping bug that was very noticeable on dial-up connections has 
	been removed.
	Many initialisation problems have been fixed by making the comms 
	packages smaller.
	
	Controls		
	Joysticks can now use the 'Z' Axis as a rudder [this was previously 
	limited to throttles].
	
	Notes
	If you update your graphics hardware with MA installed you must delete
	the savegame\settings.mig file out of the installed directory.

	Don't use EndItAll.exe or a similar program that shuts down tasks 
	if multiplayer games crash [particularly the guests] when entering 
	the 3D.

	For the 'Auto Frame Rate' preference, there is an extra option named 
	"fast". Use this option on fast machines if you suffer from "Ground 
	Stutter".
	
	General Bug Fixes
	Crack and Burn bug fixed.
	Crash when selecting trees as targets fixed.
	Crash when pressing tab/fire/pause on take-off fixed.
	Too many radio messages crash fixed.
	Music / audio thread crash fixed.
	Photo bug which seems to be generated from DX7 fixed.
	Fixed attacking bug in comms.
	Fixed a memory leak in the 3D.
	Fixed bad fuel reporting.

--------------------------------------------------------------------------------
SOMMAIRE  (Français)
--------------------------------------------------------------------------------
1	Paramètres de configuration du joystick Logitech Force Feedback
2	Configuration clavier
3	V1.02 
4	Workarounds
5	V1.03
6	V1.1
7	Multiplayer Views
8	V1.23

--------------------------------------------------------------------------------
1	Paramètres de configuration du joystick Logitech Force Feedback

Si vous utilisez un joystick "Logitech Wingman Force", nous vous recommandons de
configurer l'effet "retour au centre" sur 35%. Votre manette sera ainsi moins 
rigide et vous ressentirez moins de vibrations.

2	Configuration du clavier

Le programme Controls vous permet de reconfigurer les touches du clavier à votre
guise. Vous trouverez ce programme dans le répertoire d'installation de MiG Alley. 

3	V1.02

Fixes:-
	AWE64 Sound FX missing
	Random Crashes in the 3D [Audio triggers]
	Smoke trails going jagged
	Random Crashes in the replay [audio and accel]
	Rcombo Crashes [mainly on the Prefereneces Screen]
	Missing dialogs if Windows Font is 110% or 200%
	Improved font if 'Intel' font not installed
	USB Joysticks cooperating with other USB devices
	Memory leak going from the 3D to the preferences screen
	
4	Workarounds (V1.1)

The following issues affect some users. We will continue to fix these and other 
issues in future patches, meanwhile the workarounds described will improve the
enjoyment of affected users.

Voodoo2 and TNT2 together:
 Either	Select 800x600 or lower resolution (1024x768 is selected by default)
 Or	Disable "Voodoo 2 Direct 3D Support" to get all resolutions on the TNT2
	if the option is listed on Advanced from the Voodoo2 tab of Display 
	Properties.

No 'stencil' style font on the front screens:
	Reinstall the "Intel.ttf" truetype font which is in c:\windows\fonts 

TnT has fuzzy fonts
	Change the number of auto-generated Mip-Map levels to 0 [it
	defaults to 10]

VooDoo2 SLI mode
	If you have a problem then disable SLI support - it is listed on 
	Advanced from the Voodoo2 tab of Display Properties.

Keyboard not responding
	If the keyboard fails to respond when in the 3d then remove any 
	joystick control or profiler programs that are enabled.


Bad in game Fonts
	if you only seem to be able to get Wingdings or some other
	strange font you may need to re-install the font.
	this is called intel.ttf and can be found on the website
	[http://www.cix.co.uk/~rowan/Mig/intel.ttf]
	if this does not help then remove it and the game should choose
	a Times Roman font.

Cannot access the icons on the map toolbar
	switch off the 'Smart Move' feature of your mouse or main
	crontroller.

5	V1.03 [demo build + fixes]
	Software driver - explosions made correct colour
	Fixed Photo Zoom jitter
	Target Diamond works in software driver mode
	Ctrl-5 / enter - new view glance at instruments
	Map work :- [waypoints info, mid-level map, hi-detail map]
	removed troops from inside the hill on CAS UN attacking mission
	Flaps - now have Full up mid and down i.e.
		f 	toggles full on / full off
		shift-f	half on [or half off]
		shift-r	Full on
		shift-v Full off

6	MiG Alley: Version 1.1
	-----------------------
	November 1999
	The Sticky key problem has now been fixed

	September 1999

	This note defines the changes to V1.02 of MiG Alley.
	
	Navigation
	----------
	A mid-level zoom has been added to the map. The large-scale map has also 
	been improved.

	On the map screen the bearing and range from your aircraft to the Current 
	waypoint is displayed. For other waypoints, the bearing and range from 
	the previous waypoint is displayed. 
	In the cockpit there is an extra info line of navigational information.

	Controls
	--------
	You can glance at the instruments using either ctrl 5 or Number Pad 
	Enter.
	Mouse panning is now disabled when on the map or on sticky keys.
	A midway flaps option has been added:
		Shift r	flaps up
		Shift f	flaps midway
		Shift v	flaps down
	On most machines, the key to the left of the main keypad "1" key gives 
	zero rpm.  
	
	Graphic Glitches
	----------------
	On the CAS UN Attacking Quick Mission the troops on the hill are 
	now visible.
	The Software Driver explosions no longer use strange colours.
	On Photo zoom, the small judder on max zoom out has been removed.
	With the Software Driver, the red target diamond now follows the target 
	correctly.
	The flying crater bug has been fixed.
	An aircraft's shadow will not be visible when it has been destroyed.
	The clock hour hand moves more realistically.
	The front gear suspension on the F80 now animates realistically.
	The problems with the horizon ball have been fixed

	Game Play Issues
	----------------
	MiGs are more aggressive. You need to hit them harder before they will 
	stand-down.
	The MiGs take-off from the Southern airfields even when Sabres are in 
	the vicinity.
	In the Campaign Armed Reconn missions, vehicles can be seen travelling 
	along roads.
	Armed Reconn and CAS logic has been improved.
	It is now possible to change the targets on preplanned missions.
	Activity in Battle areas has been increased. Barrages are visible.
	On the CAS UN Defending quick mission, the mission can be completed 
	because your pilots will attack and destroy enemy forces.
	The weapons potency has been tuned to make attacks against ground forces 
	more successful.
	On the UN Fighter Bomber Strike 2 quick mission the default target is now 
	Wonju. This target is well protected by AAA. Also your aircraft will now 
	be carrying 1000lb bombs.
	If you are not the leader, you get prompted to start your attack 
	during strike missions.

7	Multiplayer Views

Restricted views.
	Restricted views prevent players from using padlocks or the pan 
	view commands. This is rather draconian and is intended to be so that 
	all players have the same restrictions.

8	MiG Alley Version 1.23
	----------------------
	Graphics
	Target Lock stutter fixed.
		
	Graphics Cards
	TnT+VooDoo2 graphics selection problem fixed. If you had two D3D 
	capable cards in your machine then it was possible to get a D3D error 
	for an illegal mode. For example this occurred when you selected 
	1024x768 for a TnT with a single VooDoo2.
		
	Flight
	F51 Speed Indicator fixed, it is now accurate up to about 500 Knots.
	
	Multiplayer
	
	Match and Team play Internet connections more stable and smooth. 
	Quick missions are improved but not perfect.
	The warping bug that was very noticeable on dial-up connections has 
	been removed.
	Many initialisation problems have been fixed by making the comms 
	packages smaller.
	
	Controls		
	Joysticks can now use the 'Z' Axis as a rudder [this was previously 
	limited to throttles].
	
	Notes
	If you update your graphics hardware with MA installed you must delete
	the savegame\settings.mig file out of the installed directory.

	Don't use EndItAll.exe or a similar program that shuts down tasks 
	if multiplayer games crash [particularly the guests] when entering 
	the 3D.

	For the 'Auto Frame Rate' preference, there is an extra option named 
	"fast". Use this option on fast machines if you suffer from "Ground 
	Stutter".
	
	General Bug Fixes
	Crack and Burn bug fixed.
	Crash when selecting trees as targets fixed.
	Crash when pressing tab/fire/pause on take-off fixed.
	Too many radio messages crash fixed.
	Music / audio thread crash fixed.
	Photo bug which seems to be generated from DX7 fixed.
	Fixed attacking bug in comms.
	Fixed a memory leak in the 3D.
	Fixed bad fuel reporting.

--------------------------------------------------------------------------------
CONTENIDOS (Español)
--------------------------------------------------------------------------------
1 	Configuración del Joystick de Logitech Force Feedback
2	Teclado
3	Solución de problemas
4	Solución de problemas (V1.1)
5	V1.03 [añadidos de esta versión - demo]
6	Versión 1.1
7	Multiplayer Views
8	V1.23

--------------------------------------------------------------------------------
1	Configuración del Joystick de Logitech Force Feedback

Si utilizas un joystick "Logitech Wingman Force", es recomendable que la opción de Efecto Muelle (Spring Effect) en el panel de control de Dispositivos de Juego este al 35%. Esto evitará una excesiva rigidez del joystick y vibraciones extrañas.

2	Teclado

El programa "Controls" puede ser utilizado para reconfigurar los controles en MiG Alley. Este programa se encuentra en el directorio donde MiG Alley haya sido instalado.

3	Solución de problemas

Los siguientes problemas pueden afectar a algunos usuarios. Si ése es tu caso,
consulta alguna de las siguientes soluciones.

Voodoo2 y TNT juntas
	Elige una resolución de 800x600 o inferior (1024x768 es la selección por defecto)
	o desactiva el "Soporte de Voodoo 2 para Direct 3D" para conseguir todas las
	resoluciones posibles con la TNT2. Esta opción podrás encontrarla en "Avanzado"
	dentro de la etiqueta de Voodoo2 en la caja de diálogo de Propiedades
	de Pantalla.

Las fuentes de los menús no se ven correctamente
	Reinstala la fuente truetype "Intel.ttf" que se encuentra en el directorio 
	c:\windows\fonts.

Las fuentes se ven borrosas con TnT
	Cambia el número de los niveles de Mip-Map autogenerados a 0 (por
	defecto es 10).

Modos SLI con Voodoo2
	Si experimentas algún problema desactiva este modo en "Avanzado" dentro de 
	de la etiqueta de Voodoo2 en la caja de diálogo de Propiedades de Pantalla.

4	Solución de problemas (V1.1)

Los siguientes problemas pueden afectar a algunos usuarios. Los siguiente problemas
pueden afectar a algunos usuarios. Seguimos intentando buscar soluciones definitivas
pero, mientras tanto, lo que se describe a continuación podría mejorar notablemente
el comportamiento del programa:

Voodoo2 y TNT juntas
O	Eliges una resolución de 800x600 o inferior (1024x768 es la selección por defecto)
o 	desactivas el "Soporte de Voodoo 2 para Direct 3D" para conseguir todas las
	resoluciones posibles con la TNT2. Esta opción podrás encontrarla en "Avanzado"
	dentro de la etiqueta de Voodoo2 en la caja de diálogo de Propiedades
	de Pantalla.

Las fuentes de los menús no se ven correctamente
	Reinstala la fuente truetype "Intel.ttf" que se encuentra en el directorio 
	"c:\windows\fonts".

Las fuentes se ven borrosas con TnT
	Cambia el número de los niveles de Mip-Map autogenerados a 0 (por
	defecto es 10).

Modos SLI con Voodoo2
	Si experimentas algún problema desactiva este modo en "Avanzado" dentro de 
	de la etiqueta de Voodoo2 en la caja de diálogo de Propiedades de Pantalla.

Keyboard not responding
	If the keyboard fails to respond when in the 3d then remove any 
	joystick control or profiler programs that are enabled.


Bad in game Fonts
	if you only seem to be able to get Wingdings or some other
	strange font you may need to re-install the font.
	this is called intel.ttf and can be found on the website
	[http://www.cix.co.uk/~rowan/Mig/intel.ttf]
	if this does not help then remove it and the game should choose
	a Times Roman font.

Cannot access the icons on the map toolbar
	switch off the 'Smart Move' feature of your mouse or main
	crontroller.

5	V1.03 [añadidos de esta versión - demo]
	Control-5 / enter - Nueva vista de los instrumentos
	Flaps - Ahora pueden subirse o bajarse completamente o por mitades.
		Por ejemplo:
		f 	Subir o bajar flaps totalmente (on/off)
		Mays.-f	Flaps a mitad de camino
		Mays.-r	Subir flaps completamente (on)
		Mays.-v Bajar flaps completamente (off)

6	MiG Alley: Versión 1.1
	-----------------------
	November 1999
	The Sticky key problem has now been fixed

	Septiembre 1999

	A continuación encontrarás una relación de las mejoras implementadas en
	esta versión:
	
	Navegación
	----------
	Se ha añadido un zoom medio al mapa y también se ha mejorado el mapa a gran
	escala.

	En la pantalla del mapa aparecen el rumbo y alcance de tu avión hasta el
	waypoint actual. Para otros waypoints, aparece el rumbo y alcance desde
	el punto de trayectoria anterior.
	
	En la cabina se ha incluido una línea extra de ifnormación adicional.


	Controles
	--------
	Puedes echar un vistazo a los instrumentos pulsando Control-5 o el Intro
	del teclado numérico.
	
	La panorámica con el ratón se desactiva en el mapa o con las teclas pegajosas.

	Se ha añadido una opción para bajar o subir los flaps hasta la mitad.
		Mays. r	flaps arriba
		Mays. f	flaps a mitad de camino
		Mays. v	flaps abajo
	En la mayoría de los ordenadores, la tecla a la izquierda del "1" en el
	teclado principal pone las rpm a cero.
	
	
	Juego
	----------------
	MiGs son más agresivos. Necesitas impactarles varias veces antes de poder derribarlos.
	Los MiGs despegan desde los los aeródromos del sur, incluso aunque haya Sabres en las
	cercanías.
	En las misiones de reconocmiento puedes observar a losvehículos moviéndose por las
	carreteras.
	Ahora es posible cambiar los objetivos de las misiones pre-planificadas.

7	Multiplayer Views

Restricted views.
	Restricted views prevent players from using padlocks or the pan 
	view commands. This is rather draconian and is intended to be so that 
	all players have the same restrictions.


8	MiG Alley Version 1.23
	----------------------
	Graphics
	Target Lock stutter fixed.
		
	Graphics Cards
	TnT+VooDoo2 graphics selection problem fixed. If you had two D3D 
	capable cards in your machine then it was possible to get a D3D error 
	for an illegal mode. For example this occurred when you selected 
	1024x768 for a TnT with a single VooDoo2.
		
	Flight
	F51 Speed Indicator fixed, it is now accurate up to about 500 Knots.
	
	Multiplayer
	
	Match and Team play Internet connections more stable and smooth. 
	Quick missions are improved but not perfect.
	The warping bug that was very noticeable on dial-up connections has 
	been removed.
	Many initialisation problems have been fixed by making the comms 
	packages smaller.
	
	Controls		
	Joysticks can now use the 'Z' Axis as a rudder [this was previously 
	limited to throttles].
	
	Notes
	If you update your graphics hardware with MA installed you must delete
	the savegame\settings.mig file out of the installed directory.

	Don't use EndItAll.exe or a similar program that shuts down tasks 
	if multiplayer games crash [particularly the guests] when entering 
	the 3D.

	For the 'Auto Frame Rate' preference, there is an extra option named 
	"fast". Use this option on fast machines if you suffer from "Ground 
	Stutter".
	
	General Bug Fixes
	Crack and Burn bug fixed.
	Crash when selecting trees as targets fixed.
	Crash when pressing tab/fire/pause on take-off fixed.
	Too many radio messages crash fixed.
	Music / audio thread crash fixed.
	Photo bug which seems to be generated from DX7 fixed.
	Fixed attacking bug in comms.
	Fixed a memory leak in the 3D.
	Fixed bad fuel reporting.
