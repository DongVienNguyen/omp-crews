"""Reconstructed, independent exercises; not production tasks or rollout evidence.

Each unit carries initial sources, explicit normal/error/boundary acceptance and
an executable oracle. Solutions exist only for offline oracle validation; runner
never places them, this module, or its own source in native writer read scope.
UI exercises test accessible server-rendered components plus their CRUD state,
not browser layout. Performance oracles measure work, not noisy wall clocks.
"""
from dataclasses import dataclass
from textwrap import dedent


@dataclass(frozen=True)
class Unit:
    id: str
    family: str
    mission: str
    need: str
    difficulty: float
    initial: str
    solution: str
    checks: tuple
    inputs: tuple = ()
    scout: bool = False

    @property
    def acceptance(self):
        return [item[0] for item in self.checks]

    @property
    def files(self):
        return {**dict(self.inputs), 'product.py': dedent(self.initial).lstrip()}

    def oracle(self):
        # Each check runs independently, so one early failure cannot hide others.
        prelude = '''import json, traceback
from pathlib import Path
import product as p
results = []
'''
        parts = [prelude]
        for criterion, source in self.checks:
            parts.append('try:\n' + ''.join('    ' + line + '\n' for line in dedent(source).strip().splitlines()))
            parts.append('except Exception:\n    results.append({"criterion": ' + repr(criterion) + ', "status": "fail"})\n')
            parts.append('else:\n    results.append({"criterion": ' + repr(criterion) + ', "status": "pass"})\n')
        parts.append('print(json.dumps({"criterion_results": results}))\nraise SystemExit(0 if all(r["status"] == "pass" for r in results) else 1)\n')
        return ''.join(parts)


def c(normal, error, boundary):
    # Preserve literal newlines in quoted fixture values as Python escapes.
    def source(text):
        out = []; quote = None; escaped = False
        for char in text:
            if quote and char == '\n':
                out.append('\\n'); continue
            out.append(char)
            if escaped: escaped = False
            elif char == '\\': escaped = True
            elif quote == char: quote = None
            elif quote is None and char in "\"'": quote = char
        return ''.join(out)
    return tuple((label, source(text)) for label, text in (normal, error, boundary))


UNITS = (
    Unit('docs-precedence', 'retrieval_docs',
         'Read handbook.md. Implement resolve(env, file, default): explicit environment value wins, then file, then default. Empty string is explicit; None means absent. Reject non-string non-None values.',
         'bounded_retrieval', 1,
         'def resolve(env, file, default): return file or env or default',
         '''
         def resolve(env, file, default):
             if any(v is not None and not isinstance(v, str) for v in (env, file, default)):
                 raise ValueError('text required')
             return next((v for v in (env, file, default) if v is not None), None)
         ''', c(
             ('Normal: environment overrides file and default', "assert p.resolve('env', 'file', 'default') == 'env'"),
             ('Error: non-text setting rejected', "try: p.resolve(0, None, 'x')\nexcept ValueError: pass\nelse: raise AssertionError('invalid accepted')"),
             ('Boundary: empty explicit setting preserved; all absent returns None', "assert p.resolve('', 'f', 'd') == ''\nassert p.resolve(None, None, None) is None")),
         (('handbook.md', '# Resolution\nEnvironment overrides file, which overrides default.\nEmpty text is a value. None denotes absence. Other types are invalid.\n'),), True),
    Unit('docs-release-table', 'retrieval_docs',
         'Extract releases from releases.md into releases(text), returning stable versions newest first as (version, date). Ignore prereleases and fenced examples; invalid stable date raises ValueError. Use calendar dates.',
         'bounded_retrieval', 1,
         'def releases(text): return []',
         '''
         import datetime, re
         def releases(text):
             rows = []; fenced = False
             for line in text.splitlines():
                 if line.startswith('```'): fenced = not fenced; continue
                 if fenced: continue
                 m = re.fullmatch(r'## (\\d+\\.\\d+\\.\\d+) \\(([^)]+)\\)', line)
                 if m:
                     datetime.date.fromisoformat(m[2]); rows.append((m[1], m[2]))
             return sorted(rows, key=lambda r: tuple(map(int, r[0].split('.'))), reverse=True)
         ''', c(
             ('Normal: extract stable versions in numeric order', "assert p.releases(Path('releases.md').read_text()) == [('2.10.0','2026-10-01'),('2.9.0','2026-09-01')]"),
             ('Error: impossible calendar date rejected', "try: p.releases('## 1.0.0 (2026-02-30)')\nexcept ValueError: pass\nelse: raise AssertionError('date accepted')"),
             ('Boundary: examples and prereleases excluded; empty text empty', "assert p.releases('```\n## 9.0.0 (2026-01-01)\n```\n## 3.0.0-rc1 (2026-01-01)') == []\nassert p.releases('') == []")),
         (('releases.md', '# Changes\n## 2.9.0 (2026-09-01)\nFixes\n## 2.10.0 (2026-10-01)\n## 3.0.0-rc1 (2026-10-20)\n'),), True),
    Unit('docs-route-index', 'retrieval_docs',
         'Implement routes(text) extracting METHOD /path from API Markdown level-two headings. Preserve order, ignore prose. Allowed methods GET POST PUT DELETE; duplicate method/path raises ValueError.',
         'bounded_retrieval', 1, 'def routes(text): return text.splitlines()',
         '''
         import re
         def routes(text):
             out = []
             for line in text.splitlines():
                 m = re.fullmatch(r'## (GET|POST|PUT|DELETE) (/\\S*)', line)
                 if m:
                     row = (m[1], m[2])
                     if row in out: raise ValueError('duplicate route')
                     out.append(row)
             return out
         ''', c(
             ('Normal: extract route headings only in source order', "assert p.routes(Path('api.md').read_text()) == [('GET','/items'),('POST','/items')]"),
             ('Error: duplicate route rejected', "try: p.routes('## GET /x\n## GET /x')\nexcept ValueError: pass\nelse: raise AssertionError('duplicate accepted')"),
             ('Boundary: prose, unsupported methods, empty document ignored', "assert p.routes('GET /x\n## PATCH /x\n### GET /y') == []\nassert p.routes('') == []")),
         (('api.md', '# API\n## GET /items\nGET /not-a-heading\n## POST /items\n'),), True),
    Unit('docs-config-owners', 'retrieval_docs',
         'Implement owners(text): parse nonblank noncomment KEY=owner lines from ownership.txt, strip surrounding whitespace, retain owner case, return mapping. Reject duplicate keys and missing equals/empty fields.',
         'bounded_retrieval', 1, 'def owners(text): return {}',
         '''
         def owners(text):
             out = {}
             for line in text.splitlines():
                 line = line.strip()
                 if not line or line.startswith('#'): continue
                 if '=' not in line: raise ValueError('assignment required')
                 key, owner = map(str.strip, line.split('=', 1))
                 if not key or not owner or key in out: raise ValueError('invalid owner')
                 out[key] = owner
             return out
         ''', c(
             ('Normal: ownership mapping follows source text', "assert p.owners(Path('ownership.txt').read_text()) == {'cache':'Infra','api':'Backend'}"),
             ('Error: duplicates and malformed entries rejected', "for text in ['x=a\nx=b', 'broken', '=a', 'x=']:\n    try: p.owners(text)\n    except ValueError: pass\n    else: raise AssertionError(text)"),
             ('Boundary: comments, whitespace and empty input handled', "assert p.owners(' # note\n\n x = Team A ') == {'x':'Team A'}\nassert p.owners('') == {}")),
         (('ownership.txt', '# Current owners\ncache = Infra\napi=Backend\n'),), True),
    Unit('transform-csv', 'exact_transform',
         'Implement convert(text): parse CSV with header name,age, return compact JSON array with stripped name and integer age. Reject missing/extra columns, empty names and negative/noninteger ages. Header alone produces [].',
         'repeatable_task', 1, 'def convert(text): return text',
         '''
         import csv, io, json
         def convert(text):
             rows = csv.reader(io.StringIO(text))
             if next(rows, None) != ['name', 'age']: raise ValueError('header')
             out = []
             for row in rows:
                 if len(row) != 2 or not row[0].strip(): raise ValueError('row')
                 age = int(row[1])
                 if age < 0: raise ValueError('age')
                 out.append({'name': row[0].strip(), 'age': age})
             return json.dumps(out, separators=(',', ':'))
         ''', c(
             ('Normal: quoted CSV converts to compact typed JSON', '''assert p.convert('name,age\n"Doe, Jo",31\n') == '[{"name":"Doe, Jo","age":31}]' '''),
             ('Error: malformed schema and age rejected', "for text in ['bad,age\na,2', 'name,age\na,-1', 'name,age\na,x', 'name,age\na,1,x', 'name,age\n,1']:\n    try: p.convert(text)\n    except ValueError: pass\n    else: raise AssertionError(text)"),
             ('Boundary: header-only and zero age supported', "assert p.convert('name,age\n') == '[]'\nassert json.loads(p.convert('name,age\na,0')) == [{'name':'a','age':0}]"))),
    Unit('transform-slug', 'exact_transform',
         'Implement slug(text): NFKD normalize, drop non-ASCII, lowercase, replace each run of non-alphanumeric characters with one hyphen, trim hyphens. Reject non-string. Empty normalization returns empty string.',
         'repeatable_task', 1, 'def slug(text): return text.lower().replace(" ", "-")',
         '''
         import re, unicodedata
         def slug(text):
             if not isinstance(text, str): raise TypeError('text')
             ascii_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
             return re.sub('[^a-z0-9]+', '-', ascii_text.lower()).strip('-')
         ''', c(
             ('Normal: normalize accents and punctuation exactly', "assert p.slug('  Café & Tea!!! ') == 'cafe-tea'"),
             ('Error: non-string rejected', "try: p.slug(None)\nexcept TypeError: pass\nelse: raise AssertionError('invalid accepted')"),
             ('Boundary: empty and non-ASCII-only values empty; digits retained', "assert p.slug('') == p.slug('東京') == ''\nassert p.slug('A__007') == 'a-007'"))),
    Unit('scaffold-package', 'exact_transform',
         'Implement scaffold(name) returning mapping of two relative files: name/__init__.py equals __version__ = "1.0.0" plus newline; pyproject.toml has [project], name quoted, version "1.0.0". Name must be ASCII Python identifier and not keyword. No disk writes.',
         'repeatable_task', 1, 'def scaffold(name): return {}',
         '''
         import keyword
         def scaffold(name):
             if not isinstance(name, str) or not name.isascii() or not name.isidentifier() or keyword.iskeyword(name):
                 raise ValueError('package name')
             return {name + '/__init__.py': '__version__ = "1.0.0"\\n', 'pyproject.toml': '[project]\\nname = "' + name + '"\\nversion = "1.0.0"\\n'}
         ''', c(
             ('Normal: emit exact package files and parseable project metadata', "import tomllib\nr=p.scaffold('sample_pkg')\nassert set(r)=={'sample_pkg/__init__.py','pyproject.toml'}\nassert r['sample_pkg/__init__.py'].splitlines()==['__version__ = \"1.0.0\"']\nassert r['sample_pkg/__init__.py'].endswith(chr(10))\nassert tomllib.loads(r['pyproject.toml'])=={'project':{'name':'sample_pkg','version':'1.0.0'}}"),
             ('Error: traversal, keywords and invalid package names rejected', "for name in ['../x','class','2x','é','']:\n    try: p.scaffold(name)\n    except ValueError: pass\n    else: raise AssertionError(name)"),
             ('Boundary: single underscore valid and generation pure', "assert '_/__init__.py' in p.scaffold('_')\nassert p.scaffold('a') == p.scaffold('a')"))),
    Unit('transform-env', 'exact_transform',
         'Implement encode(values): emit sorted KEY=JSON-string-value lines, final newline only when nonempty. Keys match [A-Z_][A-Z0-9_]*; values strings. JSON preserves Unicode; rejects invalid keys/types.',
         'repeatable_task', 1, 'def encode(values): return str(values)',
         '''
         import json, re
         def encode(values):
             if any(not isinstance(k, str) or not re.fullmatch('[A-Z_][A-Z0-9_]*', k) or not isinstance(v, str) for k,v in values.items()):
                 raise ValueError('invalid environment')
             return ''.join(k + '=' + json.dumps(values[k], ensure_ascii=False) + '\\n' for k in sorted(values))
         ''', c(
             ('Normal: sorted lines escape embedded newline and quotes', "assert p.encode({'Z':'a\nb','A':'\"'}) == 'A=' + json.dumps('\"') + '\nZ=' + json.dumps('a\nb') + '\n'"),
             ('Error: invalid names and nonstring values rejected', "for d in [{'bad':'x'},{'A':1},{'2A':'x'}]:\n    try: p.encode(d)\n    except ValueError: pass\n    else: raise AssertionError(d)"),
             ('Boundary: empty map empty and Unicode preserved', "assert p.encode({}) == ''\nassert p.encode({'_':'é'}) == '_=\"é\"\n'"))),
    Unit('ui-todo-create', 'ui_crud',
         'Build server-rendered todo component: add(items,text) returns new list of {id,text}, monotonic max+1 IDs, strips text, rejects blank. render(items) returns HTML with labeled text input id=todo, Add button and escaped list items. Do not mutate input.',
         'everyday_implementation', 1.5, 'def add(items,text): return items\ndef render(items): return ""',
         '''
         from html import escape
         def add(items, text):
             text = text.strip()
             if not text: raise ValueError('blank todo')
             return items + [{'id': max((x['id'] for x in items), default=0)+1, 'text': text}]
         def render(items):
             return '<label for="todo">Todo</label><input id="todo" name="todo"><button>Add</button><ul>' + ''.join('<li>'+escape(x['text'])+'</li>' for x in items) + '</ul>'
         ''', c(
             ('Normal: create todo with fresh ID and render accessible control', "old=[{'id':4,'text':'old'}]; new=p.add(old,' next ')\nassert new==old+[{'id':5,'text':'next'}] and len(old)==1\ns=p.render(new)\nassert 'for=\"todo\"' in s and 'id=\"todo\"' in s and '<button>Add</button>' in s and '<li>next</li>' in s"),
             ('Error: blank todo rejected without changing state', "items=[]\ntry: p.add(items,'  ')\nexcept ValueError: pass\nelse: raise AssertionError('blank accepted')\nassert items==[]"),
             ('Boundary: first ID one and HTML text escaped', "assert p.add([], 'x')[0]['id']==1\ns=p.render([{'id':1,'text':'<script>&'}])\nassert '&lt;script&gt;&amp;' in s and '<script>' not in s"))),
    Unit('ui-contact-edit', 'ui_crud',
         'Build contact edit component: update(rows,id,email) immutably updates exact ID; email must contain one @ with nonempty sides; missing ID raises KeyError. render(row) emits labeled email input and Save button, escaping attribute values.',
         'everyday_implementation', 1.5, 'def update(rows,id,email): return rows\ndef render(row): return str(row)',
         '''
         from html import escape
         def update(rows, id, email):
             if email.count('@') != 1 or any(not x for x in email.split('@')): raise ValueError('email')
             if not any(r['id']==id for r in rows): raise KeyError(id)
             return [dict(r,email=email) if r['id']==id else dict(r) for r in rows]
         def render(row):
             return '<label for="email">Email</label><input id="email" type="email" value="'+escape(row['email'],quote=True)+'"><button>Save</button>'
         ''', c(
             ('Normal: edit exact contact and render labeled email control', "rows=[{'id':1,'email':'a@b'},{'id':2,'email':'c@d'}]\nr=p.update(rows,2,'new@host')\nassert r[1]['email']=='new@host' and rows[1]['email']=='c@d' and r[0]==rows[0]\ns=p.render(r[1]); assert 'for=\"email\"' in s and 'type=\"email\"' in s and '>Save<' in s"),
             ('Error: bad email and unknown ID refused', "try: p.update([],1,'a@b')\nexcept KeyError: pass\nelse: raise AssertionError('missing accepted')\nfor email in ['x','@x','x@','x@@y']:\n    try: p.update([{'id':1}],1,email)\n    except ValueError: pass\n    else: raise AssertionError(email)"),
             ('Boundary: attribute injection escaped and singleton editable', "assert '&quot;' in p.render({'email':'\" onfocus=\"x'})\nassert p.update([{'id':0,'email':'a@b'}],0,'x@y')==[{'id':0,'email':'x@y'}]"))),
    Unit('ui-cart-delete', 'ui_crud',
         'Build cart remove component: remove(cart,sku) immutably removes matching SKU; missing SKU raises KeyError. total(cart) returns integer cents sum price*qty. render(cart) has table header Product and per-row Remove button with escaped SKU and name. Empty cart renders status Empty cart.',
         'everyday_implementation', 1.5, 'def remove(cart,sku): return []\ndef total(cart): return 0\ndef render(cart): return ""',
         '''
         from html import escape
         def remove(cart, sku):
             if not any(x['sku']==sku for x in cart): raise KeyError(sku)
             return [dict(x) for x in cart if x['sku']!=sku]
         def total(cart): return sum(x['price']*x['qty'] for x in cart)
         def render(cart):
             if not cart: return '<p role="status">Empty cart</p>'
             return '<table><tr><th>Product</th></tr>'+''.join('<tr><td>'+escape(x['name'])+'</td><td><button data-sku="'+escape(x['sku'],quote=True)+'">Remove</button></td></tr>' for x in cart)+'</table>'
         ''', c(
             ('Normal: remove only selected row; total uses integer cents', "cart=[{'sku':'a','name':'A','price':199,'qty':2},{'sku':'b','name':'B','price':50,'qty':1}]\nr=p.remove(cart,'b'); assert len(r)==1 and len(cart)==2 and p.total(cart)==448\ns=p.render(r); assert '<th>Product</th>' in s and 'data-sku=\"a\"' in s and '>Remove<' in s"),
             ('Error: unknown SKU refused without dropping items', "try: p.remove([{'sku':'a'}],'b')\nexcept KeyError: pass\nelse: raise AssertionError('unknown removed')"),
             ('Boundary: empty cart accessible; untrusted text escaped', "assert p.total([])==0 and 'role=\"status\"' in p.render([])\ns=p.render([{'sku':'\"','name':'<b>'}]); assert '&quot;' in s and '&lt;b&gt;' in s"))),
    Unit('ui-inventory-crud', 'ui_crud',
         'Build inventory component: apply(state,action) accepts create(id,name), update(id,name), delete(id), returning new dict. Names stripped nonblank; duplicate create ValueError; absent update/delete KeyError; unknown operation ValueError. render(state) lists names sorted by ID with Edit/Delete buttons and labeled Name input.',
         'everyday_implementation', 1.5, 'def apply(state,action): return state\ndef render(state): return ""',
         '''
         from html import escape
         def apply(state, action):
             op=action['op']; key=action.get('id'); out=dict(state)
             if op not in ('create','update','delete'): raise ValueError('operation')
             if op=='create' and key in out: raise ValueError('duplicate')
             if op!='create' and key not in out: raise KeyError(key)
             if op=='delete': del out[key]
             else:
                 name=action['name'].strip()
                 if not name: raise ValueError('name')
                 out[key]=name
             return out
         def render(state):
             return '<label for="name">Name</label><input id="name"><ul>'+''.join('<li>'+escape(state[k])+'<button>Edit</button><button>Delete</button></li>' for k in sorted(state))+'</ul>'
         ''', c(
             ('Normal: create update delete chain immutable; UI includes controls', "a={}; b=p.apply(a,{'op':'create','id':2,'name':' A '}); d=p.apply(b,{'op':'update','id':2,'name':'B'})\nassert a=={} and b=={2:'A'} and d=={2:'B'} and p.apply(d,{'op':'delete','id':2})=={}\ns=p.render(d); assert 'for=\"name\"' in s and '>Edit<' in s and '>Delete<' in s"),
             ('Error: duplicate, missing and invalid actions rejected', "for state, action, exc in [({1:'x'},{'op':'create','id':1,'name':'y'},ValueError),({}, {'op':'delete','id':1},KeyError),({}, {'op':'wat'},ValueError),({}, {'op':'create','id':1,'name':' '},ValueError)]:\n    try: p.apply(state,action)\n    except exc: pass\n    else: raise AssertionError(action)"),
             ('Boundary: empty UI works and names escape in stable ID order', "s=p.render({2:'z',1:'<x>'}); assert s.index('&lt;x&gt;')<s.index('z')\nassert '<ul></ul>' in p.render({})"))),
    Unit('api-pagination', 'api_contract',
         'Implement page(items,offset,limit): return {items,total,next}; offset nonnegative int (not bool), limit integer 1..100; next offset only if more rows remain. Preserve input list.',
         'everyday_implementation', 1, 'def page(items,offset,limit): return {"items":items,"total":len(items),"next":None}',
         '''
         def page(items, offset, limit):
             if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100: raise ValueError('pagination')
             end=offset+limit
             return {'items':items[offset:end], 'total':len(items), 'next':end if end<len(items) else None}
         ''', c(
             ('Normal: page contract includes total and next cursor', "assert p.page([0,1,2,3],1,2)=={'items':[1,2],'total':4,'next':3}"),
             ('Error: invalid pagination types and bounds rejected', "for offset,limit in [(-1,2),(0,0),(0,101),(True,2),(0,1.5)]:\n    try: p.page([],offset,limit)\n    except ValueError: pass\n    else: raise AssertionError((offset,limit))"),
             ('Boundary: empty, past-end and exact-end return no next cursor', "assert p.page([],0,1)=={'items':[],'total':0,'next':None}\nassert p.page([1],4,1)['items']==[]\nassert p.page([1],0,1)['next'] is None"))),
    Unit('api-conditional-write', 'api_contract',
         'Implement put(current,if_match,new_value): require exact version ETag string, return (200,new record) version increment on match, (412,unchanged copy) on mismatch; missing if_match returns 428. Current has version int and value; reject non-string new_value before update.',
         'everyday_implementation', 1.5, 'def put(current,if_match,new_value): return 200,{"version":1,"value":new_value}',
         '''
         def put(current, if_match, new_value):
             if not isinstance(new_value,str): raise ValueError('value')
             if if_match is None: return 428,dict(current)
             if if_match != '"'+str(current['version'])+'"': return 412,dict(current)
             return 200,dict(version=current['version']+1,value=new_value)
         ''', c(
             ('Normal: matching ETag updates version without mutating current', "old={'version':2,'value':'a'}\nassert p.put(old,'\"2\"','b')==(200,{'version':3,'value':'b'})\nassert old=={'version':2,'value':'a'}"),
             ('Error: missing and stale preconditions cannot write; invalid value refused', "old={'version':1,'value':'a'}\nassert p.put(old,None,'b')==(428,old) and p.put(old,'1','b')==(412,old)\ntry: p.put(old,'\"1\"',None)\nexcept ValueError: pass\nelse: raise AssertionError('invalid accepted')"),
             ('Boundary: version zero and empty string value supported', "assert p.put({'version':0,'value':'x'},'\"0\"','')==(200,{'version':1,'value':''})"))),
    Unit('api-error-envelope', 'api_contract',
         'Implement handle(raw): parse JSON object with integer a,b (not bool), return (200,{result:a//b}); malformed JSON/schema gives (400,{error:{code:bad_request}}), zero denominator gives (422,{error:{code:zero_divisor}}). No exception details returned.',
         'everyday_implementation', 1, 'def handle(raw): return 200,{"result":0}',
         '''
         import json
         def handle(raw):
             try:
                 data=json.loads(raw)
                 if not isinstance(data,dict) or set(data)!={'a','b'} or any(type(data[k]) is not int for k in data): raise ValueError('schema')
             except (ValueError,TypeError): return 400,{'error':{'code':'bad_request'}}
             if data['b']==0: return 422,{'error':{'code':'zero_divisor'}}
             return 200,{'result':data['a']//data['b']}
         ''', c(
             ('Normal: valid division returns fixed success envelope', "assert p.handle('{\"a\":9,\"b\":2}')==(200,{'result':4})"),
             ('Error: schema, JSON and zero-divisor use exact safe envelopes', "for raw in ['{','[]','{\"a\":true,\"b\":1}','{\"a\":1}']:\n    assert p.handle(raw)==(400,{'error':{'code':'bad_request'}})\nassert p.handle('{\"a\":1,\"b\":0}')==(422,{'error':{'code':'zero_divisor'}})"),
             ('Boundary: zero numerator and negative floor semantics preserved', "assert p.handle('{\"a\":0,\"b\":1}')[1]=={'result':0}\nassert p.handle('{\"a\":-1,\"b\":2}')[1]=={'result':-1}"))),
    Unit('api-idempotency', 'api_contract',
         'Implement Store.create(key,payload): nonempty string key and dict payload; first call allocates integer ID from 1 and returns (201,record); identical replay (200,same record); changed payload same key (409,None). Deep-copy input/output so clients cannot corrupt saved state.',
         'everyday_implementation', 1.5, 'class Store:\n    def create(self,key,payload): return 201,{"id":1,"payload":payload}',
         '''
         from copy import deepcopy
         class Store:
             def __init__(self): self.saved={}
             def create(self,key,payload):
                 if not isinstance(key,str) or not key or not isinstance(payload,dict): raise ValueError('request')
                 if key in self.saved:
                     old=self.saved[key]
                     return (200,deepcopy(old)) if old['payload']==payload else (409,None)
                 row={'id':len(self.saved)+1,'payload':deepcopy(payload)}
                 self.saved[key]=row
                 return 201,deepcopy(row)
         ''', c(
             ('Normal: first create and identical replay use same ID', "s=p.Store(); assert s.create('a',{'x':1})==(201,{'id':1,'payload':{'x':1}})\nassert s.create('a',{'x':1})==(200,{'id':1,'payload':{'x':1}})\nassert s.create('b',{})[1]['id']==2"),
             ('Error: conflicting replay refused and invalid key rejected', "s=p.Store(); s.create('a',{})\nassert s.create('a',{'x':1})==(409,None)\ntry: s.create('',{})\nexcept ValueError: pass\nelse: raise AssertionError('empty key')"),
             ('Boundary: nested input and returned records isolated', "s=p.Store(); body={'v':[]}; _,r=s.create('a',body); body['v'].append(1); r['payload']['v'].append(2)\nassert s.create('a',{'v':[]})==(200,{'id':1,'payload':{'v':[]}})"))),
    Unit('repair-leap-year', 'test_repair',
         'Repair days(year,month) using Gregorian leap rules. Raise ValueError for year outside 1..9999 or month outside 1..12; bool invalid. Keep integer day result.',
         'everyday_implementation', 1, 'def days(year,month):\n    return 29 if month==2 and year%4==0 else (28 if month==2 else 30)',
         '''
         import calendar
         def days(year,month):
             if type(year) is not int or type(month) is not int or not 1<=year<=9999 or not 1<=month<=12: raise ValueError('date')
             return calendar.monthrange(year,month)[1]
         ''', c(
             ('Normal: month lengths and 400-year leap rule correct', "assert [p.days(2026,m) for m in (1,4,2)]==[31,30,28]\nassert p.days(2000,2)==29 and p.days(1900,2)==28"),
             ('Error: out-of-range dates and booleans refused', "for y,m in [(0,1),(10000,1),(2026,13),(2026,0),(True,2)]:\n    try: p.days(y,m)\n    except ValueError: pass\n    else: raise AssertionError((y,m))"),
             ('Boundary: first and last supported years accepted', "assert p.days(1,1)==31 and p.days(9999,12)==31"))),
    Unit('repair-intervals', 'test_repair',
         'Repair merge(intervals): merge closed overlapping or touching intervals, sort output, no mutation. Each pair integer start<=end; invalid raises ValueError. Empty input empty.',
         'everyday_implementation', 1.5, 'def merge(intervals): return sorted(intervals)',
         '''
         def merge(intervals):
             if any(len(x)!=2 or any(type(v) is not int for v in x) or x[0]>x[1] for x in intervals): raise ValueError('interval')
             out=[]
             for a,b in sorted(intervals):
                 if out and a<=out[-1][1]: out[-1][1]=max(b,out[-1][1])
                 else: out.append([a,b])
             return out
         ''', c(
             ('Normal: nested and touching intervals coalesce without mutation', "x=[[5,7],[1,3],[3,6],[2,2]]; before=[v[:] for v in x]\nassert p.merge(x)==[[1,7]] and x==before"),
             ('Error: reversed and noninteger intervals rejected', "for x in [[[2,1]],[[0,1.5]],[[True,2]],[[1]]]:\n    try: p.merge(x)\n    except ValueError: pass\n    else: raise AssertionError(x)"),
             ('Boundary: empty, point and disjoint intervals retained', "assert p.merge([])==[]\nassert p.merge([[2,2],[0,0]])==[[0,0],[2,2]]"))),
    Unit('repair-binary-search', 'test_repair',
         'Repair first(items,target): index first equal element in sorted list or -1. Must use O(log n) indexed reads; do not copy/iterate entire input. Supports empty and repeated values.',
         'everyday_implementation', 1, 'def first(items,target):\n    for i,x in enumerate(items):\n        if x==target: return i\n    return -1',
         '''
         def first(items,target):
             lo,hi=0,len(items)
             while lo<hi:
                 mid=(lo+hi)//2
                 if items[mid]<target: lo=mid+1
                 else: hi=mid
             return lo if lo<len(items) and items[lo]==target else -1
         ''', c(
             ('Normal: first duplicate position returned', "assert p.first([1,2,2,2,4],2)==1 and p.first([1,2,3],3)==2"),
             ('Error: absent target returns -1 rather than insertion index', "assert p.first([1,3,5],4)==-1 and p.first([1],0)==-1"),
             ('Boundary: empty and large indexed input require logarithmic reads', "assert p.first([],1)==-1\nclass Indexed:\n    def __init__(self): self.reads=0\n    def __len__(self): return 1048576\n    def __getitem__(self,i):\n        assert type(i) is int and 0<=i<len(self)\n        self.reads+=1; return i\nx=Indexed(); assert p.first(x,999999)==999999 and x.reads<=23"))),
    Unit('repair-context-close', 'test_repair',
         'Repair consume(opener,parse): open resource, parse it, close exactly once on success or parse exception. Propagate original parse exception, including when close also fails. If only close fails propagate close failure; opener failure must propagate.',
         'everyday_implementation', 1.5, 'def consume(opener,parse):\n    resource=opener(); value=parse(resource); resource.close(); return value',
         '''
         def consume(opener,parse):
             resource=opener()
             try: value=parse(resource)
             except BaseException:
                 try: resource.close()
                 except BaseException: pass
                 raise
             resource.close()
             return value
         ''', c(
             ('Normal: parsed result returned and close called once', "class R:\n    n=0\n    def close(self): self.n+=1\nr=R(); assert p.consume(lambda:r,lambda x:7)==7 and r.n==1"),
             ('Error: parse exception survives failing close and resource closed once', "class R:\n    n=0\n    def close(self): self.n+=1; raise RuntimeError('close')\nr=R(); error=ValueError('parse')\ndef bad(x): raise error\ntry: p.consume(lambda:r,bad)\nexcept ValueError as exc: assert exc is error\nelse: raise AssertionError('parse swallowed')\nassert r.n==1"),
             ('Boundary: opener and success-path close failures propagate', "def opening(): raise OSError('open')\ntry: p.consume(opening,lambda r:None)\nexcept OSError: pass\nelse: raise AssertionError('open swallowed')\nclass R:\n    def close(self): raise RuntimeError('close')\ntry: p.consume(R,lambda r:None)\nexcept RuntimeError: pass\nelse: raise AssertionError('close swallowed')"))),
    Unit('security-tenant', 'architecture_security',
         'Diagnose cross-tenant read bug. Implement read(records,principal,id): authenticated principal requires tenant and user; unauthenticated raises PermissionError. Return copy of record only if ID and tenant match; absent or foreign record raises KeyError with same id (avoid enumeration). Never trust request tenant.',
         'difficult_review', 2.5, 'def read(records,principal,id): return dict(records[id])',
         '''
         def read(records,principal,id):
             if not isinstance(principal,dict) or not principal.get('tenant') or not principal.get('user'): raise PermissionError('authentication')
             record=records.get(id)
             if record is None or record['tenant']!=principal['tenant']: raise KeyError(id)
             return dict(record)
         ''', c(
             ('Normal: authenticated tenant can read own copied record', "r={1:{'tenant':'a','value':7}}; x=p.read(r,{'tenant':'a','user':'u'},1); x['value']=8\nassert r[1]['value']==7"),
             ('Error: anonymous and cross-tenant requests denied', "try: p.read({1:{'tenant':'a'}},None,1)\nexcept PermissionError: pass\nelse: raise AssertionError('anonymous allowed')\ntry: p.read({1:{'tenant':'a'}},{'tenant':'b','user':'u'},1)\nexcept KeyError as exc: assert exc.args==(1,)\nelse: raise AssertionError('tenant leak')"),
             ('Boundary: missing record uses same nondisclosing error as foreign record', "for records in [{},{1:{'tenant':'other'}}]:\n    try: p.read(records,{'tenant':'a','user':'u'},1)\n    except KeyError as exc: assert exc.args==(1,)\n    else: raise AssertionError('missing/foreign accepted')"))),
    Unit('security-path', 'architecture_security',
         'Fix file containment boundary: safe(root,name) returns resolved Path inside resolved root. Reject absolute names and any result outside root, including sibling-prefix and symlink escapes. Root itself allowed via dot. Do not open file.',
         'difficult_review', 2.5, 'from pathlib import Path\ndef safe(root,name): return Path(root)/name',
         '''
         from pathlib import Path
         def safe(root,name):
             root=Path(root).resolve(); child=Path(name)
             if child.is_absolute(): raise ValueError('absolute path')
             result=(root/child).resolve()
             if not result.is_relative_to(root): raise ValueError('escape')
             return result
         ''', c(
             ('Normal: relative path normalized inside root', "import tempfile\nwith tempfile.TemporaryDirectory() as d:\n    root=Path(d)/'root'; root.mkdir()\n    assert p.safe(root,'a/../b')==root.resolve()/'b'"),
             ('Error: traversal, absolute and sibling-prefix escapes denied', "import tempfile\nwith tempfile.TemporaryDirectory() as d:\n    root=Path(d)/'root'; root.mkdir()\n    for name in ['../root-other/file',str(Path(d).resolve()/'outside')]:\n        try: p.safe(root,name)\n        except ValueError: pass\n        else: raise AssertionError(name)"),
             ('Boundary: root allowed and resolved symlink traversal denied when OS permits symlinks', "import tempfile\nwith tempfile.TemporaryDirectory() as d:\n    root=Path(d)/'root'; root.mkdir(); assert p.safe(root,'.')==root.resolve()\n    link=root/'link'\n    try: link.symlink_to(Path(d),target_is_directory=True)\n    except OSError: pass\n    else:\n        try: p.safe(root,'link/outside')\n        except ValueError: pass\n        else: raise AssertionError('symlink escape')"))),
    Unit('security-redaction', 'architecture_security',
         'Diagnose nested secret leak. redact(value) recursively copies dict/list JSON data; case-insensitive keys password, token, authorization replaced with [REDACTED]. Preserve ordinary scalars and key spellings; reject non-JSON objects with TypeError. Input unchanged.',
         'difficult_review', 2, 'def redact(value): return {k:("[REDACTED]" if k=="password" else v) for k,v in value.items()}',
         '''
         def redact(value):
             if isinstance(value,dict):
                 if any(not isinstance(k,str) for k in value): raise TypeError('JSON key')
                 return {k:'[REDACTED]' if k.lower() in {'password','token','authorization'} else redact(v) for k,v in value.items()}
             if isinstance(value,list): return [redact(v) for v in value]
             if value is None or type(value) in (str,int,float,bool): return value
             raise TypeError('JSON value')
         ''', c(
             ('Normal: nested list and mixed-case secrets redacted without mutation', "x={'users':[{'Token':'secret','name':'A'}],'Authorization':'Bearer x'}\nr=p.redact(x); assert r=={'users':[{'Token':'[REDACTED]','name':'A'}],'Authorization':'[REDACTED]'}\nassert x['users'][0]['Token']=='secret'"),
             ('Error: unsupported objects and nonstring keys refused', "for x in [object(),{1:'x'}]:\n    try: p.redact(x)\n    except TypeError: pass\n    else: raise AssertionError('unsupported accepted')"),
             ('Boundary: empty containers and harmless scalar values preserved', "assert p.redact([{},[],None,False,0,'token'])==[{},[],None,False,0,'token']"))),
    Unit('architecture-layering', 'architecture_security',
         'Resolve dependency architecture: order(graph) returns deterministic topological initialization order with dependencies before dependents, lexicographically smallest ready node first. Missing referenced node ValueError; cycle ValueError. Do not mutate graph. Edges node -> dependencies.',
         'integration_architecture', 2.5, 'def order(graph): return sorted(graph)',
         '''
         import heapq
         def order(graph):
             deps={k:set(v) for k,v in graph.items()}
             if any(v not in deps for values in deps.values() for v in values): raise ValueError('missing dependency')
             reverse={k:[] for k in deps}
             for k,values in deps.items():
                 for v in values: reverse[v].append(k)
             ready=[k for k,v in deps.items() if not v]; heapq.heapify(ready); out=[]
             while ready:
                 k=heapq.heappop(ready); out.append(k)
                 for child in reverse[k]:
                     deps[child].remove(k)
                     if not deps[child]: heapq.heappush(ready,child)
             if len(out)!=len(deps): raise ValueError('cycle')
             return out
         ''', c(
             ('Normal: dependency-first deterministic architecture order', "g={'api':['service'],'service':['db'],'db':[],'audit':[]}\nassert p.order(g)==['audit','db','service','api'] and g['api']==['service']"),
             ('Error: missing dependencies and cycles rejected', "for g in [{'a':['x']},{'a':['b'],'b':['a']},{'a':['a']}]:\n    try: p.order(g)\n    except ValueError: pass\n    else: raise AssertionError(g)"),
             ('Boundary: empty graph and duplicated edge handled', "assert p.order({})==[]\nassert p.order({'b':['a','a'],'a':[]})==['a','b']")), scout=True),
    Unit('concurrency-counter', 'concurrency_precision',
         'Repair Counter.add(n=1) and value property for concurrent threads. Each add atomic and exact, reject bool/noninteger before mutation. Initial value zero; negative and zero deltas valid. Reads must return consistent integer snapshots during concurrent updates; locking strategy is not prescribed.',
         'everyday_implementation', 2, 'import time\nclass Counter:\n    def __init__(self): self._value=0\n    @property\n    def value(self): return self._value\n    def add(self,n=1):\n        old=self._value; time.sleep(0); self._value=old+n',
         '''
         from threading import Lock
         class Counter:
             def __init__(self): self._value=0; self._lock=Lock()
             @property
             def value(self):
                 with self._lock: return self._value
             def add(self,n=1):
                 if type(n) is not int: raise ValueError('integer delta')
                 with self._lock: self._value+=n
         ''', c(
             ('Normal: concurrent increments exact and reads are consistent snapshots', "from concurrent.futures import ThreadPoolExecutor\nfrom threading import Event\nc=p.Counter(); start=Event()\ndef work(_):\n    start.wait()\n    for i in range(100): c.add()\ndef observe():\n    start.wait()\n    for i in range(800):\n        value=c.value\n        assert type(value) is int and 0<=value<=800\nwith ThreadPoolExecutor(max_workers=9) as pool:\n    jobs=[pool.submit(work,i) for i in range(8)]; reads=pool.submit(observe); start.set()\n    for job in jobs: job.result()\n    reads.result()\nassert c.value==800"),
             ('Error: invalid delta refused before mutation', "c=p.Counter()\nfor n in [True,1.5,'1']:\n    try: c.add(n)\n    except ValueError: pass\n    else: raise AssertionError(n)\nassert c.value==0"),
             ('Boundary: zero and negative deltas exact', "c=p.Counter(); c.add(0); c.add(-3); c.add(3); assert c.value==0"))),
    Unit('precision-money', 'concurrency_precision',
         'Implement cents(text): decimal string to integer cents, ROUND_HALF_UP including negative ties. Reject NaN/Infinity and non-string; never use binary float. Accept scientific notation and signed zero.',
         'everyday_implementation', 1.5, 'def cents(text): return round(float(text)*100)',
         '''
         from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
         def cents(text):
             if not isinstance(text,str): raise ValueError('decimal string')
             try:
                 value=Decimal(text)
                 if not value.is_finite(): raise ValueError('finite required')
                 with localcontext() as ctx:
                     ctx.prec=max(28,len(value.as_tuple().digits)+abs(value.adjusted())+4)
                     return int((value*100).quantize(Decimal(1),rounding=ROUND_HALF_UP))
             except InvalidOperation as exc: raise ValueError('decimal') from exc
         ''', c(
             ('Normal: decimal half-up ties exact in both directions', "assert p.cents('1.005')==101 and p.cents('-1.005')==-101 and p.cents('2.675')==268"),
             ('Error: malformed, nonfinite and nonstring amounts rejected', "for x in ['NaN','Infinity','oops',1.2]:\n    try: p.cents(x)\n    except ValueError: pass\n    else: raise AssertionError(x)"),
             ('Boundary: signed zero scientific notation and large exact amount', "assert p.cents('-0')==0 and p.cents('1e-2')==1\nassert p.cents('123456789012345678901234567890.01')==12345678901234567890123456789001"))),
    Unit('concurrency-async-order', 'concurrency_precision',
         'Implement async collect(factories,limit): invoke/await zero-argument async factories at most limit concurrently, return results in input order. Positive integer limit required (not bool). On failure cancel and await remaining tasks before propagating original exception.',
         'everyday_implementation', 2, 'async def collect(factories,limit): return [await f() for f in factories]',
         '''
         import asyncio
         async def collect(factories,limit):
             if type(limit) is not int or limit<1: raise ValueError('limit')
             sem=asyncio.Semaphore(limit)
             async def run(factory):
                 async with sem: return await factory()
             tasks=[asyncio.create_task(run(f)) for f in factories]
             try: return await asyncio.gather(*tasks)
             except BaseException:
                 for task in tasks: task.cancel()
                 await asyncio.gather(*tasks,return_exceptions=True)
                 raise
         ''', c(
             ('Normal: bounded concurrent collection preserves source order', "import asyncio\nasync def test():\n    active=0; peak=0\n    async def job(n):\n        nonlocal active,peak\n        active+=1; peak=max(peak,active)\n        try: await asyncio.sleep(.001*(4-n)); return n\n        finally: active-=1\n    out=await p.collect([lambda n=n:job(n) for n in range(4)],2)\n    assert out==[0,1,2,3] and peak==2 and active==0\nasyncio.run(test())"),
             ('Error: worker failure drains sibling cancellation', "import asyncio\nasync def test():\n    closed=[]; started=asyncio.Event()\n    async def wait():\n        started.set()\n        try: await asyncio.sleep(60)\n        finally: closed.append(True)\n    async def bad():\n        await started.wait(); raise RuntimeError('worker')\n    try: await asyncio.wait_for(p.collect([wait,bad],2),2)\n    except RuntimeError: pass\n    else: raise AssertionError('failure swallowed')\n    assert closed==[True]\nasyncio.run(test())"),
             ('Boundary: empty collection and invalid limits handled', "import asyncio\nassert asyncio.run(p.collect([],1))==[]\nfor limit in [0,-1,True]:\n    try: asyncio.run(p.collect([],limit))\n    except ValueError: pass\n    else: raise AssertionError(limit)"))),
    Unit('precision-timestamp', 'concurrency_precision',
         'Implement epoch_us(text): parse ISO8601 timestamp with required timezone, return exact integer microseconds since UTC Unix epoch; support offsets, Z, before epoch. Reject naive or invalid timestamp. Avoid float total_seconds.',
         'everyday_implementation', 1.5, 'from datetime import datetime\ndef epoch_us(text): return int(datetime.fromisoformat(text).timestamp())*1000000',
         '''
         from datetime import datetime, timezone
         def epoch_us(text):
             value=datetime.fromisoformat(text)
             if value.tzinfo is None or value.utcoffset() is None: raise ValueError('timezone required')
             delta=value.astimezone(timezone.utc)-datetime(1970,1,1,tzinfo=timezone.utc)
             return (delta.days*86400+delta.seconds)*1000000+delta.microseconds
         ''', c(
             ('Normal: offsets and fractional timestamps exact', "assert p.epoch_us('1970-01-01T01:00:00.123456+01:00')==123456"),
             ('Error: naive and invalid timestamp refused', "for text in ['2026-01-01T00:00:00','not-date','2026-02-30T00:00:00Z']:\n    try: p.epoch_us(text)\n    except ValueError: pass\n    else: raise AssertionError(text)"),
             ('Boundary: pre-epoch microsecond and far future retain precision', "assert p.epoch_us('1969-12-31T23:59:59.999999Z')==-1\nassert p.epoch_us('9999-12-31T23:59:59.999999Z')==253402300799999999"))),
    Unit('perf-batch-fetch', 'performance_diagnosis',
         'Diagnose N+1 reads. Implement hydrate(ids,fetch_many): at most one fetch_many call with unique IDs in first-seen order, return records in original order with duplicates; missing ID KeyError. Empty input makes zero calls.',
         'difficult_review', 2, 'def hydrate(ids,fetch_many): return [fetch_many([i])[i] for i in ids]',
         '''
         def hydrate(ids,fetch_many):
             keys=list(dict.fromkeys(ids))
             if not keys: return []
             records=fetch_many(keys)
             return [records[k] for k in ids]
         ''', c(
             ('Normal: one batched read preserves order and duplicates', "calls=[]\ndef fetch(keys): calls.append(keys); return {k:str(k) for k in keys}\nassert p.hydrate([3,1,3,2],fetch)==['3','1','3','2'] and calls==[[3,1,2]]"),
             ('Error: missing batch record surfaces KeyError', "try: p.hydrate([1],lambda keys:{})\nexcept KeyError as exc: assert exc.args==(1,)\nelse: raise AssertionError('missing silently skipped')"),
             ('Boundary: empty input no fetch and singleton one read', "def no(keys): raise AssertionError('unexpected fetch')\nassert p.hydrate([],no)==[]\nassert p.hydrate([0],lambda keys:{0:None})==[None]")), scout=True),
    Unit('perf-membership', 'performance_diagnosis',
         'Diagnose quadratic filtering. Implement unseen(items,known): consume known iterable once into membership index, return items absent from known preserving duplicates/order. Inputs hashable; invalid unhashable known raises TypeError. No repeated linear known scans.',
         'difficult_review', 2, 'def unseen(items,known): return [x for x in items if x not in known]',
         'def unseen(items,known):\n    index=set(known)\n    return [x for x in items if x not in index]', c(
             ('Normal: one-shot known iterator indexed once with stable output', "assert p.unseen([2,3,2,4,3],iter([2,4]))==[3,3]"),
             ('Error: unhashable known values not silently ignored', "try: p.unseen([1],[[]])\nexcept TypeError: pass\nelse: raise AssertionError('bad key accepted')"),
             ('Boundary: linear known traversal and empty cases', "class Known:\n    def __iter__(self): return iter(range(1000))\n    def __contains__(self,x): raise AssertionError('linear scan')\nassert p.unseen(list(range(1010)),Known())==list(range(1000,1010))\nassert p.unseen([],[])==[]")), scout=True),
    Unit('perf-dag-cache', 'performance_diagnosis',
         'Diagnose repeated shared DAG evaluation. evaluate(graph,root) sums leaf integer values; internal values lists of child names. Repeated edges count repeatedly, but each node fetched once per invocation. Missing KeyError, cycle ValueError. Cache must not leak across calls.',
         'difficult_review', 2.5, 'def evaluate(graph,root):\n    value=graph[root]\n    return value if type(value) is int else sum(evaluate(graph,k) for k in value)',
         '''
         def evaluate(graph,root):
             cache={}; active=set()
             def visit(key):
                 if key in active: raise ValueError('cycle')
                 if key in cache: return cache[key]
                 active.add(key)
                 value=graph[key]
                 result=value if type(value) is int else sum(visit(k) for k in value)
                 active.remove(key); cache[key]=result
                 return result
             return visit(root)
         ''', c(
             ('Normal: shared nodes evaluated once but repeated edges contribute', "class Graph(dict):\n    def __getitem__(self,k):\n        self.reads[k]=self.reads.get(k,0)+1; return super().__getitem__(k)\ng=Graph(a=['b','c'],b=['d','d'],c=['d'],d=7); g.reads={}\nassert p.evaluate(g,'a')==21 and g.reads=={'a':1,'b':1,'c':1,'d':1}"),
             ('Error: missing node and dependency cycles fail explicitly', "try: p.evaluate({},'missing')\nexcept KeyError: pass\nelse: raise AssertionError('missing accepted')\ntry: p.evaluate({'a':['a']},'a')\nexcept ValueError: pass\nelse: raise AssertionError('cycle accepted')"),
             ('Boundary: empty sum zero and cache invocation-local', "g={'a':1}; assert p.evaluate(g,'a')==1\ng['a']=2; assert p.evaluate(g,'a')==2\nassert p.evaluate({'a':[]},'a')==0")), scout=True),
    Unit('perf-stream-topk', 'performance_diagnosis',
         'Diagnose full-sort memory use. topk(values,k) returns largest k integers descending, one pass, O(k) retained values, use heapq.nlargest or bounded min heap (no sorted/list materialization of stream). k nonnegative integer not bool; k=0 must not consume stream.',
         'difficult_review', 2, 'def topk(values,k): return sorted(values,reverse=True)[:k]',
         '''
         import heapq
         def topk(values,k):
             if type(k) is not int or k<0: raise ValueError('k')
             if k==0: return []
             return heapq.nlargest(k,iter(values))
         ''', c(
             ('Normal: one-pass top-k preserves duplicates descending', "assert p.topk(iter([5,1,9,9,2]),3)==[9,9,5]"),
             ('Error: negative and boolean k rejected', "for k in [-1,True,1.5]:\n    try: p.topk([],k)\n    except ValueError: pass\n    else: raise AssertionError(k)"),
             ('Boundary: zero consumes nothing; retained memory bounded independently of stream size', "import tracemalloc\ndef stream(): raise AssertionError('consumed'); yield 1\nassert p.topk(stream(),0)==[] and p.topk(iter([1]),4)==[1]\ntracemalloc.start()\ntry:\n    assert p.topk((i for i in range(100000)),2)==[99999,99998]\n    current,peak=tracemalloc.get_traced_memory()\n    assert peak<1024*1024, ('full stream retained',peak)\nfinally: tracemalloc.stop()")), scout=True),
)


def units():
    """Strict corpus shape check; does not execute any exercise or provider."""
    assert len(UNITS) == 32 and len({u.id for u in UNITS}) == 32
    families = {u.family for u in UNITS}
    assert len(families) == 8
    assert all(sum(u.family == f for u in UNITS) == 4 for f in families)
    assert all(len(u.checks) == 3 and u.initial != u.solution for u in UNITS)
    return UNITS
