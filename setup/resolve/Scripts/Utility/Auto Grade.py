#!/usr/bin/env python
"""
Auto Grade — applies Timon's exported PowerGrade to every clip on the
current timeline in one click.

Lives under Workspace > Scripts > Utility > Auto Grade in DaVinci Resolve.
Run it with a timeline open (any page) after cutting your clips in.
"""

import DaVinciResolveScript as dvr_script

# Path to the exported PowerGrade still (.drx). Re-export from the Gallery
# (right-click the still > Export, save as DRX Files) and update this path
# if you ever swap grades.
DRX_PATH = r"C:\Users\Timon\Documents\PowerGrade_I.Still.drx"

# 0 = No keyframes, 1 = Source Timecode aligned, 2 = Start Frames aligned
GRADE_MODE = 0


def main():
    resolve = dvr_script.scriptapp("Resolve")
    if not resolve:
        print("Auto Grade: could not connect to DaVinci Resolve.")
        return

    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        print("Auto Grade: no project is open.")
        return

    timeline = project.GetCurrentTimeline()
    if not timeline:
        print("Auto Grade: no active timeline. Open/select one first.")
        return

    track_count = timeline.GetTrackCount("video")
    applied = 0
    skipped = 0

    for track_index in range(1, track_count + 1):
        items = timeline.GetItemListInTrack("video", track_index)
        if not items:
            continue
        for item in items:
            ok = item.ApplyGradeFromDRX(DRX_PATH, GRADE_MODE)
            if ok:
                applied += 1
            else:
                skipped += 1

    print(f"Auto Grade: applied PowerGrade to {applied} clip(s)"
          + (f", {skipped} skipped." if skipped else "."))


if __name__ == "__main__":
    main()
