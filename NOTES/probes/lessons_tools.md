## What earlier attempts at this job found
These are facts from attempts that succeeded on this job; use them as you judge best.
- The socket must point into the bolt: socket_toward is minus bolt_axis. The readings' ready aims already do this and allow for the arm settling a little off its target; you can pass their numbers straight to the aim tool.
- A long move straight to the head can clip it. Stopping on the axis a few centimetres out first avoids that.
- The socket drops onto the head only when it is within about 0.2 mm of the bolt's axis and the hex flats line up. The flats repeat every 60 degrees and the window is only a few degrees wide, and nothing senses their angle: finding it is a search. When the flats are close, the head sits a little deeper on the chamfer (0.2-0.6 mm rather than 0.0-0.1 mm).
- Turning while pressing, before the socket is seated, drags it about 1 mm off the axis per 15 degrees of turn, so it then cannot drop on. A turn alone and a push alone do not. Once seated, pressing while turning is fine.
- A seated socket follows the bolt as it turns. bolt_angle says how far the bolt is from snug; up to 90 degrees per turn is fine before snug.
- The torque condition is met by any installed torque from 14 to 18 N·m: 15 or 16 is as good as 14. Once installed torque is 14 or more, tightening is finished.
- Past snug, installed torque rose about 0.57 N·m per degree of bolt turn, and the wrist lagged its command by about 0.29 degrees per N·m. So near the window every degree counts: 30 degrees past snug adds about 15 N·m. Going over 18 N·m fails the job and cannot be undone.
- Turning back loosens the bolt: installed torque falls again (one attempt went from 15.4 to 5.0 N·m with a 30 degree reverse turn).
- Before lifting off, the drive torque must be near zero (under about 0.1 N·m): a loaded socket grips the flats, and a lift then jammed at 144 N. A reverse turn of 1-3 degrees unloads it without loosening the bolt (1.5 degrees took the drive torque from 15.6 to 0.7 N·m, 1 more to 0.03); more than that starts loosening it. Lifting with aim along the bolt's axis keeps the socket straight; push follows the socket's own axis, which may be tilted.
- Wrist 3 has about one turn of travel either way (joint_pos, last value).
