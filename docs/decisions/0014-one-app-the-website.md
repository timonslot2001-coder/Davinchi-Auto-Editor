# 0014 One app: the website; the Studio Artifact is frozen

- Status: accepted
- Date: 2026-11-02
- Source: Timon, "Ik heb het idee wat we nu maar aan het bouwen zijn om te bouwen", "Ik wil gewoon dat het zo min
  mogelijk tokens kost om handelingen uit te voeren"; plan [simpler-plan.md](../simpler-plan.md)

## Context
There were three ways in that did the same things: the old dashboard (`autoedit dashboard`), the website
(`python -m webapp`) and the Studio Artifact in the Claude app ([0013](0013-studio-artifact-comment-route.md)). Every
feature was built twice (website and Studio). Every Studio click is a Claude turn (tokens) and only works while the
Studio session runs, which asks for Bypass Permissions on every start. The website costs no tokens.

## Decision
- The website is the one app. Double-clicking `autoedit.bat` opens it; the separate website start file is gone.
- On the phone the website comes through Tailscale (`python -m webapp --phone`): only this PC and the devices in
  Timon's tailnet get in, everyone else gets 403 (`webapp/phone.py`). No password or token in the repo.
- New features go into the website only. The Studio Artifact stays as it is (frozen): it keeps working while its
  session runs, but gets no new buttons.
- `autoedit dashboard` stays as a command but is no longer a way in.

## Consequences
- Half the build work per feature; nothing to keep in step between two pages.
- The phone needs the Tailscale app on the PC and the phone, logged in to the same account (one-time, Timon).
- If Tailscale is off, the phone has no AutoEdit; the Studio still works as before when its session runs.
- Reversing this means building the Studio's missing pages again.
