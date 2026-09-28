from paddle_ingest import blocks
stems = ["16345dc6-3a20-40ce-bc4c-7527a00d0696_65", "17b97659-ec5e-4b19-9d4d-a246651c74d6_688",
         "17b97659-ec5e-4b19-9d4d-a246651c74d6_689", "7f1cdfe4-7a6b-47c6-84c6-5674ee0916cd_183",
         "7f1cdfe4-7a6b-47c6-84c6-5674ee0916cd_172", "329d5c09-e3d2-497c-9008-55fc337447ed_160",
         "329d5c09-e3d2-497c-9008-55fc337447ed_156"]
for stem in stems:
    bl = [b for b in (blocks(stem) or []) if b["block_label"] not in ("image","chart","header","footer","number","seal")]
    lens = [len(b["block_content"] or "") for b in bl]
    labels = [b["block_label"] for b in bl]
    print(f"{stem[-10:]}: {len(bl)} blocks, labels {sorted(set(labels))}, lens {sorted(lens)}")
    for b in bl[:4]: print("   ", b["block_label"], repr((b["block_content"] or "")[:70]))
