"""Compare the pictures required by a Word question with the final Markji body."""
import argparse
import unicodedata
from functools import lru_cache
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import audit_docx_media as word
from check_media_refs import PIC

def require(test, message):
    if not test:
        raise ValueError(message)

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

@lru_cache(maxsize=8)
def inventory(path, _mtime, _ctime, _size):
    audit = word.audit(path)
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paras = [word.element_text(p) for p in root.iter(f"{{{word.W_NS}}}p")]
    # Older exam templates use a row of drawings followed by a row of captions.
    ns = "{"+word.W_NS+"}"
    indices = {id(el):i for i,el in enumerate(root.iter(ns+"p"),1)}
    pairs = {}
    for table in root.iter(ns+"tbl"):
        lines = [r.findall(ns+"tc") for r in table.findall(ns+"tr")]
        for pictures, captions in zip(lines,lines[1:]):
            if len(pictures)!=len(captions): continue
            for pic, cap in zip(pictures,captions):
                pp=list(pic.iter(ns+"p")); cp=list(cap.iter(ns+"p"))
                if len(pp)!=1 or len(cp)!=1: continue
                txt=word.element_text(cp[0]).strip()
                lab=re.match(r"^([A-H])[.．、]",txt)
                if lab and not word.element_text(pp[0]).strip():
                    pairs[indices[id(pp[0])]]=(ord(lab[1])-64,indices[id(cp[0])],cp[0])
    return audit, paras, pairs

def read_source(path):
    st = path.stat()
    return inventory(path, st.st_mtime_ns, st.st_ctime_ns, st.st_size)

def entries(path, start, end):
    audit, paras, pairs = read_source(path)
    require(1 <= start <= end <= len(paras), "invalid_paragraph_range")
    numbered = re.match(r"^\s*(\d+)[.．、]\s*", paras[start-1])
    if numbered:
        following = re.compile(r"^\s*" + str(int(numbered[1])+1) + r"[.．、]")
        boundary = next((i for i in range(start,len(paras)) if following.match(paras[i])), None)
        if boundary is not None:
            require(end == boundary, "question_range_does_not_end_before_next_question")
    refs = []
    answer = next((i for i in range(start,end+1) if paras[i-1].lstrip().startswith("【答案】")), end+1)
    for r in audit["references"]:
        i = r["paragraph_index"]
        if start <= i <= end:
            refs.append((r,"front" if i < answer else "back"))
    return audit["docx_sha256"], paras[start-1], refs

def check(manifest, key, body):
    data = load(manifest)
    doc = Path(manifest).parent / data["docx"]
    q = data["questions"][key]
    sha, first, refs = entries(doc, *q["paragraphs"])
    require(sha == data["docx_sha256"], "changed_docx")
    require(q["stem"].strip() and q["stem"] in first and q["stem"] in body, "wrong_question_anchor")
    decisions = q["references"]
    require(len(refs) == len(decisions), "source_reference_count_mismatch")
    text = re.split(r"(?m)^---\s*$", body, maxsplit=1)
    sides = {"front":text[0], "back":text[1] if len(text)>1 else ""}
    expected = {"front":[], "back":[]}
    slots = []
    pairs = read_source(doc)[2]
    media = data.get("files",{})
    all_ids = {}
    for (r, side), record in zip(refs, decisions):
        require(record["anchor"] == [r["paragraph_index"], r["relationship_id"]]
                and r["source_sha256"] and record["sha256"] == r["source_sha256"], "wrong_source_reference")
        action = record["action"]
        require(bool(str(record.get("reason","")).strip()), "source_decision_needs_reason")
        inferred = pairs.get(r["paragraph_index"])
        if inferred and side=="front":
            require(action=="picture" or action=="alternate", "source_option_drawing_not_accounted_for")
        if action == "text":
            require(record.get("replacement") and record["replacement"] in sides[side], "missing_transcribed_symbol")
        elif action == "decorative":
            require(record.get("reviewed") is True, "decorative_requires_visual_review")
        elif action == "alternate":
            require(any(t[0]["source_sha256"] == r["source_sha256"] and t[0]["paragraph_index"] == r["paragraph_index"] and
                        d.get("action") == "picture" for t,d in zip(refs,decisions)), "unproved_alternate")
        elif action == "picture":
            media_id = record["media_id"]
            require(isinstance(media_id,str) and media_id and all_ids.setdefault(media_id,r["source_sha256"]) == r["source_sha256"], "media_id_source_conflict")
            accepted=media.get(media_id,{})
            require(accepted.get("decision")=="accepted" and accepted.get("source_sha256")==r["source_sha256"]
                    and re.fullmatch("[0-9a-f]{64}",str(accepted.get("converted_sha256",""))),
                    "media_id_not_bound_to_accepted_source")
            if r["decision"] == "needs_review":
                require(record.get("reviewed") is True, "source_image_requires_review")
            expected[side].append(media_id)
            slot = inferred[0] if inferred else record.get("option")
            if inferred and record.get("option") is not None:
                require(record["option"]==slot,"wrong_source_option")
            if slot is not None:
                require(side == "front", "option_on_answer_side")
                slots.append((slot,media_id,inferred))
        else:
            raise ValueError("unresolved_source_reference")
    for side,ids in expected.items():
        require(PIC.findall(sides[side]) == ids, "picture_missing_extra_or_out_of_order:"+side)
    if slots:
        front = sides["front"]
        before, tag, group = front.partition("[Choice#")
        require(tag and group.startswith("fixed#"), "picture_options_require_fixed_order")
        opts = re.findall(r"(?m)^[-*]\s*(.*)$", group.split("\n]",1)[0])
        gallery = PIC.findall(before)
        for n,mid,inferred in slots:
            require(type(n) is int and 1 <= n <= len(opts), "invalid_option_slot")
            if inferred:
                _,_,cap=inferred
                # Match visible source words in order (inline objects may separate them).
                mapped={(rec["anchor"][0],rec["anchor"][1]):rec for rec in decisions}
                fragments=[]
                for el in cap.iter():
                    if el.tag=="{"+word.W_NS+"}t" and el.text: fragments.append(el.text)
                    elif el.tag in ("{"+word.V_NS+"}imagedata","{"+word.A_NS+"}blip"):
                        rid=el.get(word.R_ID) or el.get(word.R_EMBED) or el.get(word.R_LINK)
                        rec=mapped.get((inferred[1],rid),{})
                        if rec.get("action")=="text": fragments.append(rec["replacement"])
                label=chr(64+n)
                caption=re.sub(r"^[A-H][.．、]\s*","","".join(fragments).strip())
                def norm(s):return re.sub(r"\s+","",unicodedata.normalize("NFKC",s))
                locs=[opts[n-1]]+[line for line in before.splitlines()
                    if re.search(r"(?:^|[# ])"+label+r"[.．、]",line)]
                require(not caption or any(norm(caption) in norm(loc) for loc in locs),
                        "source_option_caption_missing:"+str(n))
            if mid in gallery:
                labels = (f"第{n}张图", "第"+"一二三四五六七八九十"[n-1]+"张图" if n<=10 else "")
                require(gallery[n-1:n] == [mid] and (any(label and opts[n-1].strip().startswith(label) for label in labels)), "wrong_gallery_option")
            else:
                require(mid in PIC.findall(opts[n-1]), "wrong_inline_option")

def main():
    import sys
    if sys.argv[1:2]==["check"]:
        p=argparse.ArgumentParser();p.add_argument("manifest");p.add_argument("key");p.add_argument("body",type=Path)
        a=p.parse_args(sys.argv[2:]);check(a.manifest,a.key,a.body.read_text(encoding="utf-8-sig"));return
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("docx",type=Path);p.add_argument("key");p.add_argument("start",type=int);p.add_argument("end",type=int)
    p.add_argument("output",type=Path)
    a=p.parse_args();sha,first,refs=entries(a.docx,a.start,a.end)
    rows=[dict(anchor=[r["paragraph_index"],r["relationship_id"]],sha256=r["source_sha256"],side=side,
               format=r["detected_format"],action="review",reason="") for r,side in refs]
    payload=dict(docx=str(a.docx.resolve()),docx_sha256=sha,questions={a.key:dict(paragraphs=[a.start,a.end],stem=re.sub(r"^\s*\d+[.．、]\s*","",first),references=rows)})
    with a.output.open("x",encoding="utf8") as fp: json.dump(payload,fp,ensure_ascii=False,indent=2)

if __name__=="__main__":main()
