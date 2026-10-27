-- Auto Grade
-- Applies Timon's exported PowerGrade to every clip on the current timeline
-- in one click. Lives under Workspace > Scripts > Utility > Auto Grade.
-- Run it with a timeline open (any page) after cutting your clips in.

local project = resolve:GetProjectManager():GetCurrentProject()
if not project then
    print("Auto Grade: no project is open.")
    return
end

local timeline = project:GetCurrentTimeline()
if not timeline then
    print("Auto Grade: no active timeline. Open/select one first.")
    return
end

-- Path to the exported PowerGrade still (.drx). Re-export from the Gallery
-- (right-click the still > Export, save as DRX Files) and update this path
-- if you ever swap grades.
local drxPath = [[C:\Users\Timon\Documents\PowerGrade_I.Still.drx]]

-- 0 = No keyframes, 1 = Source Timecode aligned, 2 = Start Frames aligned
local gradeMode = 0

local applied = 0
local skipped = 0
local trackCount = timeline:GetTrackCount("video")

for trackIndex = 1, trackCount do
    local items = timeline:GetItemListInTrack("video", trackIndex)
    if items then
        for _, item in ipairs(items) do
            local graph = item:GetNodeGraph()
            if graph and graph:ApplyGradeFromDRX(drxPath, gradeMode) then
                applied = applied + 1
            else
                skipped = skipped + 1
            end
        end
    end
end

if skipped > 0 then
    print("Auto Grade: applied PowerGrade to " .. applied .. " clip(s), " .. skipped .. " skipped.")
else
    print("Auto Grade: applied PowerGrade to " .. applied .. " clip(s).")
end
