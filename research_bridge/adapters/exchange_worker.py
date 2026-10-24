"""Worker: no optional Python packages; no commercial application is claimed to have run."""
import csv
import json
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "urn:QDA-XML:codebook:1.0"

def load_input(job, name):
    p = job.get("inputs",{}).get(name)
    if not p or not Path(p).is_file():
        raise ValueError("missing input: " + name)
    return Path(p)

def bib_escape(text):
    # Preserve valid Unicode; escape characters with structural meaning to BibTeX.
    replacements = {"\\":r"\textbackslash{}", "{":r"\{", "}":r"\}",
                    "%":r"\%", "&":r"\&", "_":r"\_", "$":r"\$",
                    "#":r"\#", "~":r"\textasciitilde{}", "^":r"\textasciicircum{}"}
    return "".join(replacements.get(c,c) for c in " ".join(str(text).splitlines()))

def _author_name(author, bibtex=False):
    if not isinstance(author,dict):
        raise ValueError("authors must be CSL name objects")
    literal=str(author.get("literal","")).strip()
    family=str(author.get("family","")).strip()
    given=str(author.get("given","")).strip()
    # CSL literal is explicit; the family-only multiword fallback preserves the
    # institution names used by earlier jobs rather than splitting them as people.
    institution=literal or (family if not given and len(family.split())>1 else "")
    if institution:
        return "{"+bib_escape(institution)+"}" if bibtex else institution+","
    if not family and not given:
        raise ValueError("author requires literal, family, or given")
    if bibtex:
        return "{"+bib_escape(family)+"}, "+bib_escape(given) if family and given else bib_escape(family or given)
    return (family+", "+given).strip(", ")

def bibliography(job, root):
    entries = json.loads(load_input(job,"source").read_text(encoding="utf-8-sig"))
    if not isinstance(entries,list) or not entries:
        raise ValueError("bibliography must be a nonempty array of CSL-like entries")
    seen, output = set(), []
    for i,e in enumerate(entries):
        key = str(e.get("id", "ref"+str(i+1)))
        if not re.fullmatch(r"[A-Za-z0-9_:-]+",key) or key in seen or not e.get("title"):
            raise ValueError("reference IDs must be unique safe keys and title must be present")
        seen.add(key)
        authors = e.get("author",[])
        if not isinstance(authors,list):
            raise ValueError("author must be a list of CSL name objects")
        year = str(e.get("year", ""))
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", str(e.get("DOI", "")), flags=re.I)
        if job["engine"]=="jabref":
            fields = dict(title=e["title"], author=" and ".join(_author_name(a,True) for a in authors), year=year, journal=e.get("container-title",""), doi=doi)
            output.append("@article{"+key+",\n"+",\n".join("  "+k+" = {"+(v if k=="author" else bib_escape(v))+"}" for k,v in fields.items() if v)+"\n}\n")
        else:
            fields = [("TY","JOUR"),("ID",key),("TI",e["title"])]
            fields += [("AU",_author_name(a)) for a in authors]
            fields += [("PY",year),("JO",e.get("container-title","")),("DO",doi),("ER","")]
            output.append("\n".join(k+"  - "+" ".join(str(v).splitlines()) for k,v in fields if v or k=="ER")+"\n")
    name="references.bib" if job["engine"]=="jabref" else "references.ris"
    (root/name).write_text("\n".join(output),encoding="utf-8")
    return {"references":len(entries),"scope":"file_interchange","application_verified":False}

def _qname(name):
    return "{"+NS+"}"+name

def _xml_text(value, field, required=False):
    if not isinstance(value,str) or (required and not value.strip()):
        raise ValueError(field+" must be "+("a nonempty string" if required else "a string"))
    if any(not (ord(c) in (9,10,13) or 32<=ord(c)<=0xD7FF or 0xE000<=ord(c)<=0xFFFD or 0x10000<=ord(c)<=0x10FFFF) for c in value):
        raise ValueError(field+" contains a character invalid in XML 1.0")
    return value

def _guid(value, seen=None, generate=False):
    value=str(value or (uuid.uuid4() if generate else "")).strip()
    if not re.fullmatch(r"(?:[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}|\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\})",value):
        raise ValueError("invalid codebook GUID")
    value=str(uuid.UUID(value))
    if seen is not None:
        if value in seen:
            raise ValueError("duplicate codebook GUID")
        seen.add(value)
    return value

def _color(value):
    if isinstance(value,str):
        value=value.strip()
    if not isinstance(value,str) or not re.fullmatch(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})",value):
        raise ValueError("code color must be #RGB or #RRGGBB")
    return value

def _codebook_data(data):
    codes=data.get("codes") if isinstance(data,dict) else data
    if not isinstance(codes,list) or not codes:
        raise ValueError("codebook codes must be a nonempty list")
    return codes

def codebook(job, root):
    """Export the REFI-QDA 1.0 Codebook schema, including hierarchy and sets."""
    data=json.loads(load_input(job,"source").read_text(encoding="utf-8-sig"))
    codes=_codebook_data(data)
    ET.register_namespace("",NS)
    origin=data.get("origin","DSH Research Toolkit") if isinstance(data,dict) else "DSH Research Toolkit"
    book=ET.Element(_qname("CodeBook"),{"origin":_xml_text(origin,"origin")})
    container=ET.SubElement(book,_qname("Codes"))
    ids=set()
    def add(parent,code):
        if not isinstance(code,dict):
            raise ValueError("each code must be an object")
        name=_xml_text(code.get("name"),"code name",True)
        guid=_guid(code.get("guid"),ids,True)
        codable=code.get("isCodable",True)
        if not isinstance(codable,bool):
            raise ValueError("isCodable must be a JSON boolean")
        attrs={"guid":guid,"name":name,"isCodable":"true" if codable else "false"}
        if "color" in code:
            attrs["color"]=_color(code["color"])
        node=ET.SubElement(parent,_qname("Code"),attrs)
        if "description" in code:
            ET.SubElement(node,_qname("Description")).text=_xml_text(code["description"],"description")
        children=code.get("children",[])
        if not isinstance(children,list):
            raise ValueError("code children must be a list")
        for child in children:
            add(node,child)
    for code in codes:
        add(container,code)
    code_ids=set(ids)
    sets=data.get("sets",[]) if isinstance(data,dict) else []
    if not isinstance(sets,list):
        raise ValueError("codebook sets must be a list")
    if sets:
        group=ET.SubElement(book,_qname("Sets"))
        for item in sets:
            if not isinstance(item,dict):
                raise ValueError("each set must be an object")
            node=ET.SubElement(group,_qname("Set"),{"guid":_guid(item.get("guid"),ids,True),"name":_xml_text(item.get("name"),"set name",True)})
            if "description" in item:
                ET.SubElement(node,_qname("Description")).text=_xml_text(item["description"],"description")
            members=item.get("member_guids",[])
            if not isinstance(members,list):
                raise ValueError("set member_guids must be a list")
            for member in members:
                guid=_guid(member)
                if guid not in code_ids:
                    raise ValueError("set references an unknown code GUID")
                ET.SubElement(node,_qname("MemberCode"),{"guid":guid})
    ET.indent(book)
    ET.ElementTree(book).write(root/"codebook.qdc",encoding="utf-8",xml_declaration=True)
    return {"codes":len(code_ids),"sets":len(sets),"scope":"file_interchange","application_verified":False}

def import_codebook(job, root):
    """Import validated supported REFI-QDA data without silently dropping fields.

    Runtime remains standard-library-only. The independent acceptance suite uses
    the externally sourced XSD with lxml, in addition to these semantic checks.
    """
    raw=load_input(job,"source").read_bytes()
    if len(raw)>16*1024*1024:
        raise ValueError("codebook exceeds the 16 MiB import limit")
    # Reject declarations before parsing, including UTF-16/32 encodings.
    declaration_scan=raw.replace(b"\x00",b"").upper()
    if b"<!DOCTYPE" in declaration_scan or b"<!ENTITY" in declaration_scan:
        raise ValueError("DTD/entity declarations are not allowed in codebooks")
    book=ET.fromstring(raw)
    if book.tag!=_qname("CodeBook"):
        raise ValueError("expected REFI-QDA 1.0 CodeBook root namespace")
    def attrs(node,allowed,required=()):
        if set(node.attrib)-set(allowed) or any(k not in node.attrib for k in required):
            raise ValueError("unsupported or missing codebook attribute")
    def children(node,allowed):
        if any(c.tag not in allowed for c in node):
            raise ValueError("unsupported codebook element")
        if (node.text or "").strip() or any((c.tail or "").strip() for c in node):
            raise ValueError("unexpected mixed content in codebook")
    def description(node,out):
        descriptions=node.findall(_qname("Description"))
        if len(descriptions)>1 or (descriptions and list(node)[0] is not descriptions[0]):
            raise ValueError("Description must occur once before child elements")
        if descriptions:
            d=descriptions[0]
            if d.attrib or list(d):
                raise ValueError("Description must contain only text")
            out["description"]=_xml_text(d.text or "","description")
    attrs(book,{"origin","{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"})
    children(book,{_qname("Codes"),_qname("Sets")})
    nodes=list(book)
    if not nodes or nodes[0].tag!=_qname("Codes") or len(nodes)>2 or (len(nodes)==2 and nodes[1].tag!=_qname("Sets")):
        raise ValueError("CodeBook must contain Codes followed by optional Sets")
    codes_node=nodes[0]
    attrs(codes_node,set())
    children(codes_node,{_qname("Code")})
    if not list(codes_node):
        raise ValueError("codebook must contain at least one code")
    seen=set()
    def parse_code(node):
        attrs(node,{"guid","name","isCodable","color"},("guid","name","isCodable"))
        children(node,{_qname("Description"),_qname("Code")})
        boolean=node.get("isCodable").strip()
        if boolean not in ("true","false","1","0"):
            raise ValueError("invalid isCodable boolean")
        out={"guid":_guid(node.get("guid"),seen),"name":_xml_text(node.get("name"),"code name",True),"isCodable":boolean in ("true","1")}
        if "color" in node.attrib:
            out["color"]=_color(node.get("color"))
        description(node,out)
        subcodes=node.findall(_qname("Code"))
        if subcodes:
            out["children"]=[parse_code(c) for c in subcodes]
        return out
    data={"codes":[parse_code(c) for c in codes_node]}
    if "origin" in book.attrib:
        data["origin"]=book.get("origin")
    code_ids=set(seen)
    if len(nodes)==2:
        sets_node=nodes[1]
        attrs(sets_node,set())
        children(sets_node,{_qname("Set")})
        if not list(sets_node):
            raise ValueError("Sets must contain at least one Set")
        data["sets"]=[]
        for node in sets_node:
            attrs(node,{"guid","name"},("guid","name"))
            children(node,{_qname("Description"),_qname("MemberCode")})
            out={"guid":_guid(node.get("guid"),seen),"name":_xml_text(node.get("name"),"set name",True),"member_guids":[]}
            description(node,out)
            for member in node.findall(_qname("MemberCode")):
                attrs(member,{"guid"},("guid",))
                if list(member) or (member.text or "").strip():
                    raise ValueError("MemberCode must be empty")
                guid=_guid(member.get("guid"))
                if guid not in code_ids:
                    raise ValueError("set references an unknown code GUID")
                out["member_guids"].append(guid)
            data["sets"].append(out)
    (root/"codebook.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"codes":len(code_ids),"sets":len(data.get("sets",[])),"scope":"file_interchange","application_verified":False}

def zotero(job,root):
    inputs,params=job.get("inputs",{}),job.get("parameters",{})
    op=job["operation"]
    base="http://127.0.0.1:23119/api/users/0"
    if op=="search":
        limit=int(params.get("limit",20))
        if not 1<=limit<=100:
            raise ValueError("Zotero limit must be between 1 and 100")
        query=str(params.get("query",inputs.get("query","")))
        suffix="/items?"+urllib.parse.urlencode({"q":query,"limit":limit,"format":"json"})
        output="zotero-items.json"
    else:
        key=str(params.get("key",inputs.get("key","")))
        if not re.fullmatch(r"[A-Z0-9]{8}",key):
            raise ValueError("Zotero key must be 8 uppercase alphanumeric characters")
        suffix="/items/"+key+("/children" if op=="children" else "")
        output="zotero-children.json" if op=="children" else "zotero-item.json"
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request=urllib.request.Request(base+suffix,headers={"Zotero-API-Version":"3","Accept":"application/json"})
    try:
        with opener.open(request,timeout=min(20,job.get("timeout_s",20))) as r:
            data=json.load(r)
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError,TimeoutError,ConnectionError) as e:
        print("RB_BLOCKED: Zotero local API unavailable: "+str(e),file=sys.stderr)
        return None
    if not isinstance(data,(dict,list)):
        raise ValueError("unexpected Zotero API schema")
    (root/output).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"scope":"local_api","application_verified":True,"items":len(data) if isinstance(data,list) else 1}

def main():
    job=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    root=Path(sys.argv[2]).resolve()
    op=job["operation"]
    if job["engine"]=="zotero":
        result=zotero(job,root)
        if result is None:
            return 2
    elif op=="bibliography":
        result=bibliography(job,root)
    elif op=="codebook":
        result=codebook(job,root)
    elif op=="import_codebook":
        result=import_codebook(job,root)
    elif op=="table":
        source=load_input(job,"source")
        with source.open(encoding="utf-8-sig",newline="") as f:
            reader=csv.reader(f)
            rows=list(reader)
        if len(rows)<2 or len(set(rows[0]))!=len(rows[0]) or any(len(r)!=len(rows[0]) for r in rows):
            raise ValueError("CSV requires unique headers and rectangular nonempty rows")
        with (root/"data.csv").open("w",encoding="utf-8-sig",newline="") as f:
            csv.writer(f).writerows(rows)
        result={"rows":len(rows)-1,"columns":len(rows[0]),"scope":"file_interchange","application_verified":False}
    elif op=="project":
        (root/"research.Rproj").write_text("Version: 1.0\n\nRestoreWorkspace: No\nSaveWorkspace: No\nAlwaysSaveHistory: Default\nEnableCodeIndexing: Yes\nEncoding: UTF-8\n",encoding="utf-8")
        result={"scope":"file_interchange","application_verified":False}
    else:
        raise ValueError("unsupported exchange operation")
    (root/"exchange-audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RB_EXCHANGE_COMPLETE")
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(type(e).__name__+": "+str(e),file=sys.stderr)
        raise SystemExit(1)
