# Contributing

The governing document for this repository is `README.md`.

Every contribution must strengthen and protect the Ontology SSOT against fragmentation.
Invariant #1 is non-negotiable: all production data access and transformations must route through `ontology/client.py` or a stricter ontology boundary layered on top of it.
If a change adds or alters ontology meaning, update `/ontology/` first and then update the Constitution in `README.md`.
