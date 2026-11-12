SYNTHETIC: invented test matter; every company, person, figure and date in this file is made up.

# Replay fixture: the untagged twin over the loopback stub

`sent/` holds the six calls a run of the untagged twin, `report/draft-untagged.md`, made to `fixture/stub_model.py` with provider `chat` and the invented model id `synthetic-proposer-1`. `verdicts.json` is what that run gave. Each `NNNN-request.json` is the exact body the chat adapter sent and each `NNNN-response.json` the exact body the stub returned, with no headers. Replay finds an answer by the sha256 of the request body, so these files keep their bytes and carry no marker line of their own. This README is their marker.

To replay them, set `provider` to `replay`, `model` to `synthetic-proposer-1`, `draft` to `report/draft-untagged.md` and `replay_from` to `replay/untagged-chat` in a copy of matter 1 that holds this folder. The run's `verdicts.json` then equals the one here byte for byte, with no socket opened.

A change to `prompts/propose.txt`, to the chunk message `claims.py` builds or to the chat request body changes the request hashes, and replay then stops with exit 2. Rebuild the fixture with `python3 -I tieout/fixture/stub_model.py --record`.
