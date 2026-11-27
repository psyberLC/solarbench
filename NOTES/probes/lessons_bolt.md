## What to send each round
Go down this table and send the command of the FIRST row whose condition is true now. Do not skip rows, do not go back to earlier rows' reasons, and do not reconsider once a row matches: the table was worked out from attempts that succeeded on this job. "Ready" commands are printed in every round's readings; copy them exactly. "Depth" means how far the head top is inside the socket (negative: the face is short of it). Angles are in degrees unless marked rad.

| Row | If now | Send |
|---|---|---|
| 1 | installed torque >= 14 N·m and the face is more than 30 mm short of the head top | {"done": true} |
| 2 | installed torque >= 14 N·m and drive torque > 0.1 N·m | {"turn_deg": -(0.15 × drive torque + 0.6)} |
| 3 | installed torque >= 14 N·m | the ready "put it 50 mm out" command |
| 4 | engaged = 1 and bolt_angle >= -0.06 rad | {"turn_deg": T} with T = 31 − 1.75 × installed torque, at most 20 |
| 5 | engaged = 1 | {"push_mm": P, "turn_deg": T} with P = 5 − depth in mm (0 if negative) and T = (−bolt_angle in degrees) − 2, at most 90 |
| 6 | depth > 1.5 mm | {"push_mm": 5 − depth in mm} |
| 7 | the face is more than 10 mm short of the head top, or the offset from the axis is more than 3 mm | the ready "put it 50 mm out" command, then next round row 8 |
| 8 | the face is more than 1 mm short of the head top, or the offset is more than 0.2 mm, or the tilt is more than 0.5° | the ready "centre it 0.5 mm out from the head top" command |
| 9 | wrist 3 (last joint_pos) is above 4.5 rad | {"turn_deg": -60} |
| 10 | you have not yet pushed at this wrist 3 angle (within 0.02 rad; see your Log) | {"push_mm": 1.5 + how far the face is short of the head top, in mm (0 if the head is inside)} |
| 11 | you have pushed at this wrist 3 angle | {"turn_deg": 4} if that push left the head 0.15 mm or more inside, else {"turn_deg": 10} |

Why, briefly (no need to re-derive): the socket drops onto the head only when centred within about 0.2 mm and the hex flats line up (they repeat every 60°, window of a few degrees), which rows 8, 10 and 11 search for; turning while pressing before it is seated drags it off the axis, so rows 10 and 11 never combine them; once seated, rows 5 and 4 run the bolt down and tighten it, and row 4's T lands near 15.5 N·m in two steps; rows 2 and 3 unload the wrist and lift along the axis, because a loaded or tilted socket jams on the head.

## Log
Your replies stay in the conversation (your thinking may not). Begin every reply with one line: "Log: row <n>; wrist <wrist 3 rad>; depth <mm>; offset <mm>; pushes so far <list of wrist angle: depth reached>". Copy the "pushes so far" list from your previous Log line and add to it when your last command was a push. Then end the reply with the command as one line of JSON, and nothing after it.
