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
            row={'kind':'node','commit':COMMIT,'node':item['node'],'npm':item['npm'],'status':'passed','frontend':622,'frontend_suites':dict(support.FRONTEND_COUNTS),'theme_js':97,'package_lock_sha256':support.digest(ROOT/'package-lock.json')}
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


class NodeEvidenceTests(unittest.TestCase):
    # Copied summaries from the current successful npm/frontend and theme JS logs.
    FRONTEND_LOG = """TOTAL 31 passed
TOTAL 33 workflow tests passed
TOTAL 15 control tests passed
TOTAL 19 media and news tests passed
TOTAL 36 recovery edge tests passed (Node/jsdom)
TOTAL 13 enterprise preview tests passed
TOTAL 68 refactor boundary checks passed (Node/jsdom)
TOTAL 7 catalog bulk publish checks passed (Node/jsdom)
TOTAL 31 passed, 0 failed (Node/jsdom static login demo)
TOTAL 28 presentation checks passed
TOTAL 254 pagination checks passed (Node/jsdom)
TOTAL 5 extensions guide tests passed
TOTAL 82 palette checks passed
"""
    GROUP_LOGS = {
        'frontend': FRONTEND_LOG,
        'navigation': '78 navigation DOM scenarios passed (3 Django script versions).\n',
        'enhancements': 'TOTAL 8 search enhancement tests passed\n',
        'captcha': 'TOTAL 11 CAPTCHA enhancement tests passed\n',
    }

    def logs(self, root):
        logs = root / 'logs'
        logs.mkdir()
        for name, content in self.GROUP_LOGS.items():
            (logs / (name + '.log')).write_text(content)
        data = {
            'runtime': {'node': 'v24.21.0', 'npm': '11.19.0'},
            'steps': [{'name': name, 'exitCode': 0, 'signal': None} for name in
                      ['npm-version', 'install', 'dependency-tree', 'frontend', 'navigation', 'enhancements', 'captcha']],
            'inputs': {name: support.digest(ROOT / name) for name in ['package.json', 'package-lock.json']},
            'dependency-tree': {},
        }
        for name, content in data.items():
            (logs / (name + '.json')).write_text(json.dumps(content))
        return logs

    def collect(self, root):
        return support.collect_node(root / 'logs', root / 'output', COMMIT, '24.21.0', '11.19.0')

    def test_current_logs_record_all_622_checks_including_palettes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.logs(root)
            result = self.collect(root)
            self.assertEqual(result['frontend'], 622)
            self.assertEqual(len(result['frontend_suites']), 13)
            self.assertEqual(result['frontend_suites']['palettes'], 82)
            self.assertEqual(sum(result['frontend_suites'].values()), 622)
            self.assertEqual(json.loads((root / 'output/report.json').read_text()), result)

    def test_every_frontend_suite_requires_exactly_one_success_summary(self):
        for summary in self.FRONTEND_LOG.splitlines():
            for change in ('missing', 'duplicate', 'failed', 'wrong-count'):
                with self.subTest(summary=summary, change=change), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    logs = self.logs(root)
                    altered = {'missing': '', 'duplicate': summary + '\n' + summary,
                               'failed': summary.replace('passed', 'failed'),
                               'wrong-count': summary.replace(summary.split()[1], '0', 1)}[change]
                    (logs / 'frontend.log').write_text(self.FRONTEND_LOG.replace(summary + '\n', altered + '\n'))
                    with self.assertRaisesRegex(ValueError, 'Node test evidence: frontend'):
                        self.collect(root)
                    self.assertFalse((root / 'output').exists())

    def test_same_total_cannot_hide_an_absent_suite(self):
        # Omit the 82 palette checks but add those 82 to pagination: still 622.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = self.logs(root)
            content = self.FRONTEND_LOG.replace('TOTAL 82 palette checks passed\n', '').replace('TOTAL 254', 'TOTAL 336')
            (logs / 'frontend.log').write_text(content)
            with self.assertRaises(ValueError): self.collect(root)

    def test_prior_palette_suite_counts_are_rejected(self):
        for prior_count in (50, 66):
            with self.subTest(prior_count=prior_count), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = self.logs(root)
                (logs / 'frontend.log').write_text(self.FRONTEND_LOG.replace('TOTAL 82 palette', f'TOTAL {prior_count} palette'))
                with self.assertRaises(ValueError): self.collect(root)

    def test_every_theme_js_group_rejects_missing_duplicate_or_failed_summary(self):
        for group in ('navigation', 'enhancements', 'captcha'):
            for change in ('missing', 'duplicate', 'failed'):
                with self.subTest(group=group, change=change), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    logs = self.logs(root)
                    content = self.GROUP_LOGS[group]
                    content = {'missing': '', 'duplicate': content * 2,
                               'failed': content.replace('passed', 'failed')}[change]
                    (logs / (group + '.log')).write_text(content)
                    with self.assertRaisesRegex(ValueError, 'Node test evidence: ' + group): self.collect(root)

    def test_failed_test_line_cannot_be_hidden_by_success_summary(self):
        for group in self.GROUP_LOGS:
            with self.subTest(group=group), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = self.logs(root)
                (logs / (group + '.log')).write_text('FAIL example assertion\n' + self.GROUP_LOGS[group])
                with self.assertRaises(ValueError): self.collect(root)

    def test_nonzero_command_is_rejected_despite_success_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = self.logs(root)
            steps = support.read(logs / 'steps.json')
            steps[-1]['exitCode'] = 1
            (logs / 'steps.json').write_text(json.dumps(steps))
            with self.assertRaisesRegex(ValueError, 'Incomplete Node commands'): self.collect(root)

    def test_gate_rejects_stale_or_incomplete_frontend_counts(self):
        changes = [lambda x: x.update(frontend=540), lambda x: x.update(frontend=590),
                   lambda x: x.update(frontend=606),
                   lambda x: x.pop('frontend_suites'),
                   lambda x: x['frontend_suites'].pop('palettes'),
                   lambda x: x['frontend_suites'].update(palettes=50),
                   lambda x: x['frontend_suites'].update(palettes=66)]
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                paths = MatrixTests().reports(root, 'quick')
                node = paths[-1]
                report = support.read(node)
                change(report)
                node.write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, 'Node report'):
                    support.verify_reports(root, 'quick', COMMIT, WHEEL_SHA)


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
