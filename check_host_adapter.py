"""Offline checks for private host attachment boundary. Never opens live policy/state."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from crews import omp_adapter as adapter
from omp_server import RoleSpec


class HostAdapterChecks(unittest.TestCase):
 def test_public_role_rejects_host_fields(self):
  role={'name':'retrieve','kind':'research','mission':'Read original source','deliverable':'Source evidence','answers':{'need':'bounded_retrieval','difficulty':0.5,'divisible':0,'specific':1},'scope':[],'commands':[],'acceptance':['Original sources cited']}
  for field in ('host_binding','host_binding_digest','host_tools'):
   with self.subTest(field=field),self.assertRaises(ValueError):RoleSpec.model_validate({**role,field:{}})

 def test_attachment_is_single_use_and_descriptor_only(self):
  with tempfile.TemporaryDirectory() as folder:
   state=Path(folder)/'state';project=Path(folder)/'project';project.mkdir()
   descriptor={'version':1,'tools':[{'name':'workspace_read','schema_hash':'a'*64}],'result_schema':{'type':'string'},'limits':{'max_output_tokens':10,'max_input_bytes':1000,'max_output_bytes':1000},'deadline':int(time.time()*1000)+60000}
   plan={'waves':[{'calls':[{'role_id':'retrieve'}]}]}
   with adapter.database(state) as db:
    db.execute("INSERT INTO calls VALUES(?,?,?,?,?)",('test','retrieve','prompt','planned',None))
   # load_run remains responsible for canonical identity/policy validation.
   with patch.object(adapter,'load_run',return_value=plan):
    binding=adapter.attach_host_binding('test','retrieve',str(project),'session',descriptor,state)
    self.assertEqual(binding['digest'],adapter.binding_digest(descriptor))
    self.assertEqual(plan['waves'][0]['calls'][0]['host_binding'],binding)
    with self.assertRaisesRegex(ValueError,'already attached'):adapter.attach_host_binding('test','retrieve',str(project),'session',descriptor,state)
    with adapter.database(state) as db:db.execute("UPDATE calls SET status='admitted' WHERE run='test'")
    with self.assertRaisesRegex(ValueError,'unconsumed'):adapter.attach_host_binding('test','retrieve',str(project),'session',descriptor,state)
 def test_cross_language_descriptor_digests(self):
  node=shutil.which('node')
  self.assertIsNotNone(node,'Node required for actual cross-language digest validation')
  result=subprocess.run([node,str(Path(__file__).with_name('check_host_binding.mjs')),'--binding-cases'],check=True,capture_output=True,text=True,encoding='utf-8')
  cases=json.loads(result.stdout)
  self.assertEqual(len(cases),7)
  self.assertEqual([case['descriptor']['result_schema']['minimum'] for case in cases[:4]],[1e-6,1e21,0,1/3])
  for index,case in enumerate(cases):
   with self.subTest(index=index),tempfile.TemporaryDirectory() as folder:
    descriptor=case['descriptor']
    self.assertEqual(adapter.binding_digest(descriptor),case['digest'])
    self.assertEqual(adapter.binding_digest(descriptor['result_schema']),descriptor['tools'][0]['schema_hash'])
    state=Path(folder)/'state';project=Path(folder)/'project';project.mkdir()
    plan={'waves':[{'calls':[{'role_id':'retrieve'}]}]}
    with adapter.database(state) as db:db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('test','retrieve','prompt','planned',None))
    with patch.object(adapter,'load_run',return_value=plan):
     attached=adapter.attach_host_binding('test','retrieve',str(project),'session',descriptor,state)
    self.assertEqual(attached['digest'],case['digest'],'adapter computes digest from validated descriptor, not caller hash')
    self.assertEqual(attached['descriptor'],descriptor,'canonicalization must not replace schema values')
 def test_canonical_types_and_invalid_json(self):
  self.assertEqual(adapter.binding_digest(1),hashlib.sha256(b'["number","3ff0000000000000"]').hexdigest())
  self.assertEqual(adapter.binding_digest(-0.0),adapter.binding_digest(0))
  self.assertEqual(adapter.binding_digest('\U00010000'),adapter.binding_digest('\ud800\udc00'))
  self.assertEqual(adapter.binding_digest({'\ue000':1,'\U00010000':2}),adapter.binding_digest({'\U00010000':2,'\ue000':1}))
  self.assertNotEqual(adapter.binding_digest([1]),adapter.binding_digest({'0':1}))
  self.assertNotEqual(adapter.binding_digest(True),adapter.binding_digest(1))
  self.assertNotEqual(adapter.binding_digest(None),adapter.binding_digest('null'))
  for value in (float('nan'),float('inf'),float('-inf'),10**1000,{1:'invalid'},(1,),{'\U00010000':1,'\ud800\udc00':2}):
   with self.subTest(value=repr(value)),self.assertRaises(ValueError):adapter.binding_digest(value)
  descriptor={'version':1,'tools':[],'result_schema':{},'limits':{'max_output_tokens':10,'max_input_bytes':1000,'max_output_bytes':1000},'deadline':4102444800000}
  invalid=[{**descriptor,'version':True},{**descriptor,'deadline':9007199254740992},{**descriptor,'limits':{**descriptor['limits'],'max_input_bytes':9007199254740992}}]
  invalid.extend({**descriptor,'result_schema':{'minimum':value}} for value in (float('nan'),float('inf'),float('-inf'),object()))
  for value in invalid:
   with self.subTest(descriptor=repr(value)),self.assertRaises(ValueError),patch.object(adapter,'database',side_effect=AssertionError('invalid descriptor reached state')):
    adapter.attach_host_binding('unused','unused','unused','unused',value)

 def test_invalid_descriptor_refused_before_state(self):
  for descriptor in ({},{'version':2}, {'version':1,'tools':[],'result_schema':{},'limits':{},'deadline':0}):
   with self.subTest(descriptor=descriptor),self.assertRaises(ValueError):adapter.attach_host_binding('unused','unused','unused','unused',descriptor)


if __name__=='__main__':unittest.main()
