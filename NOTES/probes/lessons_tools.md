## What earlier attempts at this job found
These are facts from attempts that succeeded on this job; use them as you judge best.
- The socket must point into the bolt: socket_toward is minus bolt_axis. The readings' ready aims already do this and allow for the arm settling a little off its target; you can pass their numbers straight to the aim tool.
- A long move straight to the head can clip it. Stopping on the axis a few centimetres out first avoids that.
- The socket drops onto the head only when it is within about 0.2 mm of the bolt's axis and the hex flats line up. The flats repeat every 60 degrees and the window is only a few degrees wide, and nothing senses their angle: finding it is a search. When the flats are close, the head sits a little deeper on the chamfer (0.2-0.6 mm rather than 0.0-0.1 mm).
- Turning while pressing, before the socket is seated, drags it about 1 mm off the axis per 15 degrees of turn, so it then cannot drop on. A turn alone and a push alone do not. Once seated, pressing while turning is fine.
- A seated socket follows the bolt as it turns. bolt_angle says how far the bolt is from snug; up to 90 degrees per turn is fine before snug.
- Past snug, installed torque rose about 0.57 N·m per degree of bolt turn, and the wrist lagged its command by about 0.29 degrees per N·m. Going over 18 N·m fails the job and cannot be undone.
- Before lifting off, the drive torque must be near zero (under about 0.1 N·m): a loaded socket grips the flats, and a lift then jammed at 144 N. A small reverse turn unloads it without loosening the bolt. Lifting with aim along the bolt's axis keeps the socket straight; push follows the socket's own axis, which may be tilted.
- Wrist 3 has about one turn of travel either way (joint_pos, last value).
