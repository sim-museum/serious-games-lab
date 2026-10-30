/* HEADTRACK-2 (PO 10-25: TrackIR 5 Pro plugged in): linuxtrack -> opentrack "UDP over network" bridge for the Rowan ports.

   MiG Alley and Battle of Britain (SRC/compat/rowan_headtrack.cpp) read six little-endian doubles per pose -- x, y, z (cm),
   yaw, pitch, roll (degrees) -- on 127.0.0.1:4242. linuxtrack drives the TrackIR and gives the pose in degrees and mm;
   this sends it on at about 100 Hz. Runs until killed.
   usage: ltr_udp_bridge [port] [linuxtrack profile]     (defaults 4242, "Default")
          ltr_udp_bridge --blobs   print the points linuxtrack sees, once a second, for 30 s (no UDP)
   build: cc -O2 -o ltr_udp_bridge ltr_udp_bridge.c -I$HOME/opt/linuxtrack/include \
            -L$HOME/opt/linuxtrack/lib/linuxtrack -Wl,-rpath,$HOME/opt/linuxtrack/lib/linuxtrack -llinuxtrack */
#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#include <math.h>

#include <linuxtrack.h>

static int blobs_mode(void)
{
	for (int i = 0; i < 30; ++i) {
		linuxtrack_pose_t pose;
		float blobs[3 * 10];
		int n = 0;
		int r = linuxtrack_get_pose_full(&pose, blobs, 10, &n);
		printf("[blobs] %s frame %u res %ux%u ret %d n %d:", linuxtrack_explain(linuxtrack_get_tracking_state()), pose.counter,
		       pose.resolution_x, pose.resolution_y, r, n);
		for (int b = 0; b < n && b < 10; ++b) printf(" (%.0f,%.0f s%.0f)", blobs[3 * b], blobs[3 * b + 1], blobs[3 * b + 2]);
		printf("  yaw %.1f pitch %.1f\n", pose.yaw, pose.pitch);
		fflush(stdout);
		sleep(1);
	}
	return 0;
}

int main(int argc, char **argv)
{
	const int blobs = argc > 1 && !strcmp(argv[1], "--blobs");
	if (blobs) argc = 1;
	const int port = argc > 1 ? atoi(argv[1]) : 4242;
	const char *profile = argc > 2 ? argv[2] : "Default";
	linuxtrack_state_type st = linuxtrack_init(profile);
	if (st < LINUXTRACK_OK) {
		fprintf(stderr, "ltr_udp_bridge: %s\n", linuxtrack_explain(st));
		return 1;
	}
	if (blobs) return blobs_mode();
	int s = socket(AF_INET, SOCK_DGRAM, 0);
	struct sockaddr_in to;
	memset(&to, 0, sizeof to);
	to.sin_family = AF_INET;
	to.sin_port = htons(port);
	to.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	uint32_t last = 0, held_blobs = 0, held_jump = 0;
	time_t said = 0;
	double acc[6] = { 0 };
	int have = 0, held = 0;
	for (;;) {
		st = linuxtrack_get_tracking_state();
		if (st == RUNNING) {	/* every tick: this linuxtrack never advances the pose counter (10-25), so "new data" is never flagged */
			/* HEADTRACK-3 (PO 10-25: leaning in/out "causes another view to flash momentarily at irregular intervals"):
			   a frame where the camera does not see all three clip LEDs, or the pose jumps further than a head can move in
			   10 ms, is a tracking glitch -- hold the last good pose (re-sync after 200 ms so a real fast move is never
			   frozen), then smooth: light on the angles, heavier on the lean, linuxtrack's noisiest axis. */
			linuxtrack_pose_t p;
			float blobs[3 * 10];
			int nb = 0;
			linuxtrack_get_pose_full(&p, blobs, 10, &nb);
			/* mm -> cm; linuxtrack's left-right is the mirror of opentrack's, which the games use (PO 10-25: "left and right are
			   reversed", up/down right) -- so yaw, roll and sideways lean change sign together. */
			const double cur[6] = { -p.tx / 10.0, p.ty / 10.0, p.tz / 10.0, -p.yaw, p.pitch, -p.roll };
			int glitch = 0;
			if (nb != 3) glitch = 1;
			else if (have && (fabs(cur[3] - acc[3]) > 30.0 || fabs(cur[4] - acc[4]) > 30.0 || fabs(cur[5] - acc[5]) > 30.0
			                  || fabs(cur[0] - acc[0]) > 6.0 || fabs(cur[1] - acc[1]) > 6.0 || fabs(cur[2] - acc[2]) > 6.0)) glitch = 2;
			if (glitch && have && held < 20) {
				++held;
				if (glitch == 1) ++held_blobs; else ++held_jump;
			} else {
				held = 0;
				for (int i = 0; i < 6; ++i) {
					const double a = !have ? 1.0 : i < 3 ? 0.15 : 0.5;
					acc[i] += a * (cur[i] - acc[i]);
				}
				have = 1;
			}
			sendto(s, acc, sizeof acc, 0, (struct sockaddr *)&to, sizeof to);
			++last;
		}
		if (time(0) - said >= 5) {	/* one status line every 5 s, so a stalled tracker or a glitch burst is visible */
			said = time(0);
			fprintf(stderr, "ltr_udp_bridge: %s, sent %u -> 127.0.0.1:%d, held: %u lost-LED frames, %u jump frames\n",
			        linuxtrack_explain(st), last, port, held_blobs, held_jump);
		}
		usleep(10000);
	}
}
