import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
support = load('ci_support')
artifacts = load('ci_artifacts')
COMMIT = 'a' * 40
WHEEL_SHA = 'b' * 64

class MatrixTests(unittest.TestCase):
    def test_quick_is_eight_variants_and_one_node(self):
        result = support.plan('quick')
        self.assertEqual(len(result['python']['include']), 3)
        self.assertEqual(sum(4 if x['captcha'] else 2 for x in result['python']['include']), 8)
        self.assertEqual([x['node'] for x in result['node']['include']], ['24.21.0'])

    def test_full_is_twenty_eight_variants_and_three_nodes(self):
        result = support.plan('full')
        self.assertEqual(len(result['python']['include']), 7)
        self.assertTrue(all(x['captcha'] for x in result['python']['include']))
        self.assertEqual(len(result['node']['include']), 3)

    def test_unknown_profile_fails(self):
        with self.assertRaises(ValueError): support.plan('ALL')

    def test_quick_must_be_subset(self):
        original = support.read
        def altered(path):
            data = original(path)
            if path.name == 'matrix.json': data['quick_python'][0]['python'] = '3.99.0'
            return data
        with patch.object(support, 'read', altered), self.assertRaises(ValueError): support.plan('quick')

    def test_duplicate_node_fails(self):
        original = support.read
        def altered(path):
            data = original(path)
            if path.name == 'matrix.json': data['node'].append(copy.deepcopy(data['node'][0]))
            return data
        with patch.object(support, 'read', altered), self.assertRaises(ValueError): support.plan('full')

    def reports(self, root, scope='full'):
        paths = []
        plan = support.plan(scope)
        for item in plan['python']['include']:
            cell = item['python'] + '/' + item['django']
            row = {'kind':'python','commit':COMMIT,'cell':cell,'captcha':item['captcha'],'status':'passed','wheel_sha256':WHEEL_SHA,'results':[]}
            for profile in (['core','captcha'] if item['captcha'] else ['core']):
                for mode in ['source','wheel']:
                    row['results'].append({'id':f'{cell}/{profile}/{mode}','status':'passed','python':item['python'],'django':item['django'],'profile':profile,'mode':mode,'steps':{name:{'status':'passed','exit_code':0,'tests_run':22 if profile=='captcha' else 270,'unittest_summary':'OK'} for name in ['venv','install','pipcheck','provenance','check','migrations','tests']}})
            directory=root/('python-'+cell.replace('/','-'));directory.mkdir();path=directory/'report.json';path.write_text(json.dumps(row));paths.append(path)
        for item in plan['node']['include']:
            row={'kind':'node','commit':COMMIT,'node':item['node'],'npm':item['npm'],'status':'passed','frontend':540,'theme_js':97,'package_lock_sha256':support.digest(ROOT/'package-lock.json')}
            directory=root/('node-'+item['node']);directory.mkdir();path=directory/'report.json';path.write_text(json.dumps(row));paths.append(path)
        return paths

    def test_reports_require_every_exact_cell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);paths=self.reports(root)
            result=support.verify_reports(root,'full',COMMIT,WHEEL_SHA)
            self.assertEqual(result['python_variants'],28)
            paths[-1].unlink()
            with self.assertRaises(ValueError): support.verify_reports(root,'full',COMMIT,WHEEL_SHA)

    def mutate_report(self, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);paths=self.reports(root);data=json.loads(paths[0].read_text());mutate(data);paths[0].write_text(json.dumps(data))
            with self.assertRaises(ValueError):support.verify_reports(root,'full',COMMIT,WHEEL_SHA)

    def test_report_commit_mismatch(self):self.mutate_report(lambda x:x.update(commit='c'*40))
    def test_report_wheel_mismatch(self):self.mutate_report(lambda x:x.update(wheel_sha256='c'*64))
    def test_missing_variant(self):self.mutate_report(lambda x:x['results'].pop())
    def test_duplicate_variant(self):self.mutate_report(lambda x:x['results'].append(x['results'][0]))
    def test_failed_step(self):self.mutate_report(lambda x:x['results'][0]['steps']['tests'].update(exit_code=1))
    def test_skipped_step(self):self.mutate_report(lambda x:x['results'][0]['steps'].pop('migrations'))

    def test_actual_python_mismatch(self):self.mutate_report(lambda x:x['results'][0].update(python='3.99.0'))
    def test_zero_tests_refused(self):self.mutate_report(lambda x:x['results'][0]['steps']['tests'].update(tests_run=0))
    def test_failed_test_summary_refused(self):self.mutate_report(lambda x:x['results'][0]['steps']['tests'].update(unittest_summary='FAILED'))

    def test_full_reports_not_mislabeled_quick(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.reports(root)
            with self.assertRaises(ValueError):support.verify_reports(root,'quick',COMMIT,WHEEL_SHA)

    def test_duplicate_report_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);paths=self.reports(root);extra=root/'duplicate';extra.mkdir();(extra/'report.json').write_bytes(paths[0].read_bytes())
            with self.assertRaises(ValueError):support.verify_reports(root,'full',COMMIT,WHEEL_SHA)

    def test_sidebars_reject_changed_wheel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wheelhouse=root/'wheels';wheelhouse.mkdir()
            filename=next(iter(support.read(ROOT/'ci/matrix.json')['django_wheels'].values()))['filename']
            (wheelhouse/filename).write_bytes(b'wrong wheel')
            with self.assertRaises(ValueError):support.sidebars(wheelhouse,root/'sidebars')

class ArtifactTests(unittest.TestCase):
    def test_paths_refuse_traversal_and_hidden_files(self):
        for name in ['../secret','/tmp/file','a/../b','.env','a//b','a\\b','a/.git/config','']:
            with self.subTest(name=name),self.assertRaises(ValueError):artifacts.safe_name(name)

    def test_static_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'static.tar.gz';files={'index.html':b'<h1>Hello</h1>','js/app.js':b'export {};','assets/README.txt':b'Local synthetic media credits'}
            artifacts.pack_static(files,target,1)
            self.assertEqual(artifacts.read_static(target),files)

    def test_static_build_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a.gz',Path(tmp)/'b.gz'
            artifacts.pack_static({'index.html':b'ok'},a,1);artifacts.pack_static({'index.html':b'ok'},b,1)
            self.assertEqual(a.read_bytes(),b.read_bytes())

    def test_static_rejects_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'bad.gz'
            with tarfile.open(target,'w:gz') as archive:
                item=tarfile.TarInfo('index.html');item.type=tarfile.SYMTYPE;item.linkname='/etc/passwd';archive.addfile(item)
            with self.assertRaises(ValueError):artifacts.read_static(target)

    def test_static_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'bad.gz'
            with tarfile.open(target,'w:gz') as archive:
                for _ in range(2):
                    item=tarfile.TarInfo('index.html');item.size=1;archive.addfile(item,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):artifacts.read_static(target)

    def test_static_source_rejects_zip_db_and_environment(self):
        for name in ['source.zip','data.sqlite3','.env']:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'dist').mkdir();(root/'dist/index.html').write_text('ok');(root/'dist'/name).write_text('bad')
                with self.subTest(name=name),self.assertRaises(ValueError):artifacts.static_files(root)

    def test_known_export_marker_is_retained(self):
        files=artifacts.static_files(ROOT)
        self.assertEqual(files[artifacts.STATIC_MARKER],artifacts.MARKER_CONTENT)

    def test_source_commit_mismatch(self):
        with patch.object(artifacts.subprocess,'check_output',return_value='b'*40+'\n'),self.assertRaises(ValueError):artifacts.source_identity(ROOT,COMMIT)

    def test_dirty_source_refused(self):
        with patch.object(artifacts.subprocess,'check_output',side_effect=[COMMIT+'\n',' M package.json\n']),self.assertRaises(ValueError):artifacts.source_identity(ROOT,COMMIT)

    def test_output_inside_checkout_refused(self):
        with self.assertRaises(ValueError):artifacts.build(ROOT,ROOT/'unsafe-artifact',COMMIT)

    def test_candidate_unknown_commit_refused_before_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'MANIFEST.json').write_text(json.dumps({'schema':1,'commit':COMMIT}))
            with self.assertRaises(ValueError):artifacts.verify(root,ROOT,'b'*40)

    def test_candidate_extra_file_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'MANIFEST.json').write_text(json.dumps({'schema':1,'commit':COMMIT,'files':{}}));(root/'SHA256SUMS').write_text('');(root/'private.env').write_text('bad')
            with self.assertRaises(ValueError):artifacts.verify(root,ROOT,COMMIT)

if __name__=='__main__':unittest.main()
