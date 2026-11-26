"""Local checks for source-to-card completeness. No real media IDs or accounts."""
import json, tempfile, unittest
from pathlib import Path
from test_media_safety import make_docx
from test_change_journal import plan
import change_journal as cj
import docx_coverage as cov

class CoverageTests(unittest.TestCase):
    def test_missing_source_cannot_begin_or_verify(self):
        j=cj.make_journal(plan()); x=j['items'][0];del x['source_material']
        for action in ['begin','verify']:
            with self.assertRaisesRegex(cj.JournalError,'source_material_required'):
                cj.apply(j,action,x['key'])
        self.assertEqual(x['status'],'planned')

    def test_docx_stops_even_when_card_has_no_picture_tags(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);doc=root/'orig.docx';make_docx(doc)
            sha,stem,refs=cov.entries(doc,1,2);m=root/'proof.json'
            rs=[dict(anchor=[r['paragraph_index'],r['relationship_id']],sha256=r['source_sha256'],
                     action='picture',media_id=str(i),reviewed=True,reason='fixture') for i,(r,_) in enumerate(refs)]
            files={v['media_id']:dict(decision='accepted',source_sha256=v['sha256'],converted_sha256='a'*64) for v in rs}
            j=cj.make_journal(plan()); x=j['items'][0];k=x['key'];x['source_material']={'docx_manifest':str(m)}
            m.write_text(json.dumps(dict(docx=str(doc),docx_sha256=sha,files=files,questions={k:dict(stem=stem,paragraphs=[1,2],references=rs)})),encoding='utf8')
            for tags in ('','[Pic#ID/0#]','[Pic#ID/1#][Pic#ID/0#]','[Pic#ID/0#][Pic#ID/0#]'):
                x['expected']['content']=stem+tags
                with self.assertRaisesRegex(cj.JournalError,'picture_missing'):
                    cj.apply(j,'begin',k)
                self.assertEqual(x['status'],'planned')
            x['expected']['content']=stem+'[Pic#ID/0#][Pic#ID/1#]'
            cj.apply(j,'begin',k)
            cj.apply(j,'receipt',k,card_id=x['bound_card_id'])
            m.unlink()
            with self.assertRaisesRegex(cj.JournalError,'docx_media_blocked'):
                cj.apply(j,'verify',k,actual=x['expected'])
            self.assertEqual(x['status'],'written')
    def test_vml_table_preserves_four_slots_and_per_option_captions(self):
        from zipfile import ZipFile
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); doc=root/"source.docx"; original=root/"seed.docx"; make_docx(original)
            labels="ABCD"; caps=["read "+v for v in labels]
            pics=lambda i: '<w:tc><w:p><w:r><w:pict><v:imagedata r:id="r%d"/></w:pict></w:r></w:p></w:tc>'%i
            cap=lambda i: '<w:tc><w:p><w:r><w:t>'+labels[i]+'. '+caps[i]+'</w:t></w:r></w:p></w:tc>'
            table="".join("<w:tr>"+fn(i)+fn(i+1)+"</w:tr>" for i in (0,2) for fn in (pics,cap))
            with ZipFile(original) as seed, ZipFile(doc,"w") as z:
                z.writestr("[Content_Types].xml",seed.read("[Content_Types].xml"))
                z.writestr("word/document.xml",f'<w:document xmlns:w="{cov.word.W_NS}" xmlns:v="{cov.word.V_NS}" xmlns:r="{cov.word.R_ID[1:].split("}")[0]}"><w:body><w:p><w:r><w:t>1. Stem</w:t></w:r></w:p><w:tbl>{table}</w:tbl></w:body></w:document>')
                rels="".join(f'<Relationship Id="r{i}" Target="media/{i}.png"/>' for i in range(4))
                z.writestr("word/_rels/document.xml.rels",f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
                for i in range(4):z.writestr(f"word/media/{i}.png",seed.read("word/media/image2.png")+bytes([i]))
            sha,_,refs=cov.entries(doc,1,9); self.assertEqual(len(refs),4)
            rows=[dict(anchor=[r["paragraph_index"],r["relationship_id"]],sha256=r["source_sha256"],action="picture",media_id=str(i),reason="checked") for i,(r,_) in enumerate(refs)]
            files={str(i):dict(decision="accepted",source_sha256=r["sha256"],converted_sha256=r["sha256"]) for i,r in enumerate(rows)}
            m=root/"plan.json";m.write_text(json.dumps(dict(docx=str(doc),docx_sha256=sha,files=files,questions={"q":dict(stem="Stem",paragraphs=[1,9],references=rows)})),encoding="utf8")
            tags=["[Pic#ID/%s#]"%i for i in range(4)]
            body="Stem\n"+"".join(tags)+"\n"+"\n".join(v+". "+c for v,c in zip(labels,caps))+"\n[Choice#fixed#\n- 第一张图\n- 第二张图\n- 第三张图\n* 第四张图\n]"
            cov.check(m,"q",body)
            for bad in (body.replace(tags[2],""),body.replace("".join(tags),""),body.replace(tags[0]+tags[1],tags[1]+tags[0]),body.replace("C. read C","D. read C"),body.replace("第二张图","第三张图")):
                with self.assertRaises(ValueError):cov.check(m,"q",bad)
if __name__=='__main__':unittest.main()
