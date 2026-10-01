# Actionable Home and easier connections

Branch: codex/league-aware-season · PR #4.

- ROS owned players have a translucent red row, left marker and My team badge; connected Sleeper roster becomes the initial profile.
- Lineup reports now include current bench and reserve players (engine 3). Older saved reports prompt refresh.
- Home shows lineup actions, injuries, data checks, matchup context and review/refresh links.
- Platform-first setup discovers Sleeper leagues from one username. Public ESPN selects teams by name and saves starters/bench. Private leagues use assisted snapshots.
- CBS native roster overview CSV is accepted with complete starter/bench count checks. CSV lacks injury designations; Unknown is retained.

## Private league status

The user signed in on CBS. Its actual roster was read and saved in the local dashboard browser: 10 starters and eight bench players, with available injury designations. No league changes were submitted. Downloaded exports and snapshots remain local and untracked. ESPN supplied URL requires sign-in; that roster remains outstanding.

## Handoff

Manual CBS/ESPN snapshots do not automatically sync, drive ROS ownership or provide start/sit projections. ROS ownership remains connected Sleeper only. Next: finish the signed-in ESPN assisted import, then extend manual ownership using verified player identities. Keep unknown statuses and missing projections explicit. Frozen draft data was not modified.
