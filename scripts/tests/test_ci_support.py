import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import zipfile
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
    def test_slider_ci_source_matches_vendored_revision_and_dependency_version(self):
        source = support.read(ROOT / 'ci/matrix.json')['slider_source']
        vendor = support.read(ROOT / 'dist/vendor/nova-slider-captcha/manifest.json')
        profile = support.read(ROOT / 'django-theme/scripts/test-matrix.json')['slider']
        self.assertEqual(source['commit'], vendor['commit'])
        self.assertEqual(source['version'], vendor['version'])
        self.assertEqual(source['version'], profile['nova-slider-captcha'])
        self.assertTrue(source['url'].endswith('/' + source['commit']))

    def test_quick_is_ten_variants_and_one_node(self):
        result = support.plan('quick')
        self.assertEqual(len(result['python']['include']), 4)
        self.assertEqual(sum(4 if x['captcha'] else 2 for x in result['python']['include']), 10)
        self.assertEqual([x['node'] for x in result['node']['include']], ['24.21.0'])

    def test_full_is_thirty_two_variants_and_three_nodes(self):
        result = support.plan('full')
        self.assertEqual(len(result['python']['include']), 8)
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
            row={'kind':'node','commit':COMMIT,'node':item['node'],'npm':item['npm'],'status':'passed','frontend':support.FRONTEND_TOTAL,'frontend_suites':dict(support.FRONTEND_COUNTS),'theme_js':294,'package_lock_sha256':support.digest(ROOT/'package-lock.json')}
            directory=root/('node-'+item['node']);directory.mkdir();path=directory/'report.json';path.write_text(json.dumps(row));paths.append(path)
        return paths

    def test_reports_require_every_exact_cell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);paths=self.reports(root)
            result=support.verify_reports(root,'full',COMMIT,WHEEL_SHA)
            self.assertEqual(result['python_variants'],32)
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

    def test_sidebar_and_filter_scripts_come_from_the_same_verified_wheel(self):
        for missing_filter in (False, True):
            with self.subTest(missing_filter=missing_filter), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);wheelhouse=root/'wheels';wheelhouse.mkdir();wheel=wheelhouse/'django-test.whl'
                with zipfile.ZipFile(wheel,'w') as archive:
                    archive.writestr('django-5.2.17.dist-info/METADATA','Version: 5.2.17\n')
                    archive.writestr('django/contrib/admin/static/admin/js/nav_sidebar.js','native sidebar')
                    if not missing_filter:archive.writestr('django/contrib/admin/static/admin/js/filters.js','native filters')
                config={'django_wheels':{'5.2.17':{'filename':wheel.name,'sha256':support.digest(wheel)}}}
                with patch.object(support,'read',return_value=config):
                    if missing_filter:
                        with self.assertRaisesRegex(ValueError, '5.2.17.*filters.js'):support.sidebars(wheelhouse,root/'scripts')
                    else:
                        rows=support.sidebars(wheelhouse,root/'scripts')
                        self.assertEqual((root/'scripts'/rows[0]['file']).read_text(),'native sidebar')
                        self.assertEqual((root/'scripts'/rows[0]['filters_file']).read_text(),'native filters')
                        self.assertEqual(rows[0]['filters_sha256'],support.digest(root/'scripts'/rows[0]['filters_file']))


class FrontendContractTests(unittest.TestCase):
    def test_checkout_npm_test_sequence_matches_the_registered_contract(self):
        names = support.frontend_contract()
        self.assertEqual(len(names), 20)
        self.assertEqual(names[-6:], ['icons', 'analytics', 'chart-libraries', 'analysis-lab', 'shared-css', 'navigation'])
        self.assertEqual(support.FRONTEND_TOTAL, 1401)

    def altered_package(self, mutation):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = support.read(ROOT / 'package.json')
            mutation(package['scripts'])
            (root / 'package.json').write_text(json.dumps(package))
            with self.assertRaisesRegex(ValueError, 'frontend suite contract'):
                support.frontend_contract(root)

    def test_missing_duplicate_reordered_and_unregistered_suite_commands_fail(self):
        changes = {
            'missing': lambda s: s.update(test=s['test'].replace(' && npm run test:icons', '')),
            'missing-users-data': lambda s: s.update(test=s['test'].replace(' && npm run test:users-data', '')),
            'duplicate': lambda s: s.update(test=s['test'] + ' && npm run test:icons'),
            'reordered': lambda s: s.update(test=s['test'].replace('npm run test:icons && npm run test:analytics', 'npm run test:analytics && npm run test:icons')),
            'unregistered': lambda s: s.update(test=s['test'] + ' && npm run test:new', **{'test:new': 'node tests/new.cjs'}),
            'compound': lambda s: s.update(test=s['test'].replace('npm run test:icons', 'npm run test:icons; true')),
        }
        for name, change in changes.items():
            with self.subTest(change=name): self.altered_package(change)

    def test_missing_or_empty_npm_script_definitions_fail(self):
        for name in ('format:check', 'check', 'test:icons', 'test:shared-css', 'test:users-data'):
            for missing in (True, False):
                with self.subTest(name=name, missing=missing):
                    self.altered_package(lambda s: s.pop(name) if missing else s.update({name: ''}))


class NodeEvidenceTests(unittest.TestCase):
    # Copied summaries from the current successful npm/frontend and theme JS logs.
    FRONTEND_LOG = """TOTAL 31 passed
TOTAL 33 workflow tests passed
TOTAL 15 control tests passed
TOTAL 19 media and news tests passed
TOTAL 36 recovery edge tests passed (Node/jsdom)
TOTAL 62 user data checks passed (Node/jsdom)
TOTAL 13 enterprise preview tests passed
TOTAL 68 refactor boundary checks passed (Node/jsdom)
TOTAL 7 catalog bulk publish checks passed (Node/jsdom)
TOTAL 48 passed, 0 failed (Node/jsdom static login demo)
TOTAL 52 presentation checks passed
TOTAL 254 pagination checks passed (Node/jsdom)
TOTAL 5 extensions guide tests passed
TOTAL 165 palette checks passed
TOTAL 361 icon checks passed
TOTAL 64 analytics checks passed
TOTAL 77 chart library checks passed
TOTAL 63 analysis lab checks passed
TOTAL 4 shared login CSS checks passed
TOTAL 24 preview navigation scenarios passed
"""
    GROUP_LOGS = {
        'frontend': FRONTEND_LOG,
        'navigation': '123 navigation DOM scenarios passed (3 Django script versions).\n25 command palette DOM scenarios passed.\n24 appearance DOM scenarios passed (3 Django script versions).\n',
        'enhancements': 'TOTAL 38 changelist enhancement tests passed\n26 print DOM scenarios passed.\n26 message DOM scenarios passed.\n',
        'captcha': 'TOTAL 16 CAPTCHA enhancement tests passed\n',
        'captcha-dialog': 'TAP version 13\n1..16\n# tests 16\n# pass 16\n# fail 0\n# cancelled 0\n# skipped 0\n# todo 0\n',
    }

    def logs(self, root):
        logs = root / 'logs'
        logs.mkdir()
        for name, content in self.GROUP_LOGS.items():
            (logs / (name + '.log')).write_text(content)
        data = {
            'runtime': {'node': 'v24.21.0', 'npm': '11.19.0'},
            'steps': [{'name': name, 'exitCode': 0, 'signal': None} for name in
                      ['npm-version', 'install', 'dependency-tree', 'frontend', 'navigation', 'enhancements', 'captcha', 'captcha-dialog']],
            'inputs': {name: support.digest(ROOT / name) for name in ['package.json', 'package-lock.json']},
            'dependency-tree': {},
        }
        for name, content in data.items():
            (logs / (name + '.json')).write_text(json.dumps(content))
        return logs

    def collect(self, root):
        return support.collect_node(root / 'logs', root / 'output', COMMIT, '24.21.0', '11.19.0')

    def test_current_log_fixture_records_all_1401_checks_in_twenty_suites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.logs(root)
            result = self.collect(root)
            self.assertEqual(result['frontend'], 1401)
            self.assertEqual(result['theme_js'], 294)
            self.assertEqual(len(result['frontend_suites']), 20)
            self.assertEqual(result['frontend_suites']['users-data'], 62)
            self.assertEqual(result['frontend_suites']['palettes'], 165)
            self.assertEqual(sum(result['frontend_suites'].values()), 1401)
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

    def test_pre_search_fix_presentation_summary_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = self.logs(root)
            (logs / 'frontend.log').write_text(self.FRONTEND_LOG.replace(
                'TOTAL 52 presentation checks passed', 'TOTAL 39 presentation checks passed'))
            with self.assertRaisesRegex(ValueError, 'Node test evidence: frontend'):
                self.collect(root)
            self.assertFalse((root / 'output').exists())

    def test_pre_user_data_fix_frontend_log_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = self.logs(root)
            (logs / 'frontend.log').write_text(self.FRONTEND_LOG.replace(
                'TOTAL 62 user data checks passed (Node/jsdom)\n', ''))
            with self.assertRaisesRegex(ValueError, 'Node test evidence: frontend'):
                self.collect(root)
            self.assertFalse((root / 'output').exists())

    def test_same_total_cannot_hide_an_absent_suite(self):
        # Omit the 165 palette checks but add those 165 to pagination: still 1401.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = self.logs(root)
            content = self.FRONTEND_LOG.replace('TOTAL 165 palette checks passed\n', '').replace('TOTAL 254', 'TOTAL 419')
            (logs / 'frontend.log').write_text(content)
            with self.assertRaises(ValueError): self.collect(root)

    def test_same_total_cannot_hide_redistributed_suite_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = self.logs(root)
            content = self.FRONTEND_LOG.replace('TOTAL 165 palette', 'TOTAL 164 palette').replace('TOTAL 361 icon', 'TOTAL 362 icon')
            (logs / 'frontend.log').write_text(content)
            with self.assertRaisesRegex(ValueError, 'Node test evidence: frontend'): self.collect(root)

    def test_unknown_and_reordered_success_summaries_are_rejected(self):
        lines = self.FRONTEND_LOG.splitlines()
        changed_order = [lines[1], lines[0], *lines[2:]]
        for content in (self.FRONTEND_LOG + 'TOTAL 1 unknown suite passed\n', self.FRONTEND_LOG + 'TOTAL\t1 malformed summary\n', self.FRONTEND_LOG + 'TOTAL\n', '\n'.join(changed_order) + '\n'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = self.logs(root)
                (logs / 'frontend.log').write_text(content)
                with self.assertRaisesRegex(ValueError, 'Node test evidence: frontend'): self.collect(root)

    def test_prior_palette_suite_counts_are_rejected(self):
        for prior_count in (50, 66, 82):
            with self.subTest(prior_count=prior_count), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = self.logs(root)
                (logs / 'frontend.log').write_text(self.FRONTEND_LOG.replace('TOTAL 165 palette', f'TOTAL {prior_count} palette'))
                with self.assertRaises(ValueError): self.collect(root)

    def test_every_theme_js_group_rejects_missing_duplicate_or_failed_summary(self):
        for group in ('navigation', 'enhancements', 'captcha'):
            for change in ('missing', 'duplicate', 'failed', 'wrong-count'):
                with self.subTest(group=group, change=change), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    logs = self.logs(root)
                    content = self.GROUP_LOGS[group]
                    content = {'missing': '', 'duplicate': content * 2,
                               'failed': content.replace('passed', 'failed'),
                               'wrong-count': content.replace(content.split()[1] if content.startswith('TOTAL') else content.split()[0], '0', 1)}[change]
                    (logs / (group + '.log')).write_text(content)
                    with self.assertRaisesRegex(ValueError, 'Node test evidence: ' + group): self.collect(root)

    def test_modal_tap_evidence_requires_all_tests_and_no_failed_or_skipped_cases(self):
        content = self.GROUP_LOGS['captcha-dialog']
        for changed in ('', content * 2, content.replace('# tests 16', '# tests 15'),
                        content.replace('# pass 16', '# pass 15'),
                        content.replace('# fail 0', '# fail 1'),
                        content.replace('# skipped 0', '# skipped 1'),
                        'not ok 1 - modal login\n' + content):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = self.logs(root)
                (logs / 'captcha-dialog.log').write_text(changed)
                with self.assertRaisesRegex(ValueError, 'Node test evidence: captcha-dialog'):
                    self.collect(root)

    def test_failed_test_line_cannot_be_hidden_by_success_summary(self):
        for group in self.GROUP_LOGS:
            with self.subTest(group=group), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = self.logs(root)
                (logs / (group + '.log')).write_text('FAIL example assertion\n' + self.GROUP_LOGS[group])
                with self.assertRaises(ValueError): self.collect(root)

    def test_enhancement_scripts_require_original_and_feature_summaries(self):
        for group in ('navigation', 'enhancements'):
            lines = self.GROUP_LOGS[group].splitlines(keepends=True)
            for index in range(len(lines)):
                for change in ('missing', 'duplicate', 'wrong-count'):
                    with self.subTest(group=group, index=index, change=change), tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        logs = self.logs(root)
                        line = lines[index]
                        number = line.split()[1] if line.startswith('TOTAL') else line.split()[0]
                        altered = {'missing': '', 'duplicate': line * 2,
                                   'wrong-count': line.replace(number, '0', 1)}[change]
                        (logs / (group + '.log')).write_text(''.join(lines).replace(line, altered))
                        with self.assertRaisesRegex(ValueError, 'Node test evidence: ' + group):
                            self.collect(root)

    def test_pre_navigation_merge_summaries_are_rejected(self):
        for group, old in [('frontend', self.FRONTEND_LOG.replace('TOTAL 24 preview navigation scenarios passed\n', '')),
                           ('navigation', self.GROUP_LOGS['navigation'].replace('123 navigation', '78 navigation'))]:
            with self.subTest(group=group), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = self.logs(root)
                (logs / (group + '.log')).write_text(old)
                with self.assertRaisesRegex(ValueError, 'Node test evidence: ' + group):
                    self.collect(root)

    def test_stale_enhancement_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = self.logs(root)
            (logs / 'enhancements.log').write_text('TOTAL 32 changelist enhancement tests passed\n')
            with self.assertRaisesRegex(ValueError, 'Node test evidence: enhancements'):
                self.collect(root)

    def test_nonzero_command_is_rejected_despite_success_summaries(self):
        for index in range(7):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = self.logs(root)
                steps = support.read(logs / 'steps.json')
                steps[index]['exitCode'] = 1
                (logs / 'steps.json').write_text(json.dumps(steps))
                with self.assertRaisesRegex(ValueError, 'Incomplete Node commands'): self.collect(root)

    def test_stale_package_and_lock_input_hashes_are_rejected(self):
        for name in ('package.json', 'package-lock.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = self.logs(root)
                inputs = support.read(logs / 'inputs.json')
                inputs[name] = '0' * 64
                (logs / 'inputs.json').write_text(json.dumps(inputs))
                with self.assertRaisesRegex(ValueError, 'Node test inputs differ from checkout'): self.collect(root)
                self.assertFalse((root / 'output').exists())

    def test_missing_duplicate_signalled_and_errored_steps_are_rejected(self):
        changes = [lambda rows: rows.pop(), lambda rows: rows.append(dict(rows[0])),
                   lambda rows: rows[0].update(signal='SIGTERM'), lambda rows: rows[0].update(error='spawn failed')]
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = self.logs(root)
                steps = support.read(logs / 'steps.json')
                change(steps)
                (logs / 'steps.json').write_text(json.dumps(steps))
                with self.assertRaisesRegex(ValueError, 'Incomplete Node commands'): self.collect(root)

    def test_summary_only_collection_has_a_distinct_kind_and_cannot_pass_the_ci_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = self.logs(root)
            # The local summary check needs only real suite logs, no fabricated steps.
            for name in ('runtime.json', 'steps.json', 'inputs.json', 'dependency-tree.json'):
                (logs / name).unlink()
            result = support.check_node_summaries(logs)
            self.assertEqual(result['kind'], 'node-suite-contract')
            self.assertEqual(result['frontend'], 1401)
            self.assertIn('no install, runtime, step', result['boundary'])
            self.assertNotIn('commit', result)
            self.assertNotIn('node', result)
            # Even adding a commit cannot turn this limited record into a Node report.
            (root / 'report.json').write_text(json.dumps({**result, 'commit': COMMIT}))
            with self.assertRaisesRegex(ValueError, 'Unknown report kind'):
                support.verify_reports(root, 'quick', COMMIT, WHEEL_SHA)

    def test_gate_rejects_stale_or_incomplete_frontend_counts(self):
        changes = [lambda x: x.update(frontend=1335), lambda x: x['frontend_suites'].pop('users-data'), lambda x: x.update(frontend=1322), lambda x: x['frontend_suites'].update(presentation=39), lambda x: x.update(theme_js=230), lambda x: x.update(frontend=1298), lambda x: x.update(theme_js=97), lambda x: x.update(theme_js=121), lambda x: x.update(frontend=540), lambda x: x.update(frontend=590),
                   lambda x: x.update(frontend=606), lambda x: x.update(frontend=622), lambda x: x.update(frontend=1270),
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

    def test_exact_vendor_notice_paths_survive_static_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'dist').mkdir();(root/'dist/index.html').write_text('ok')
            for name in artifacts.STATIC_VENDOR_NOTICES:
                target=root/'dist'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'Unchanged upstream notice')
            files=artifacts.static_files(root);archive=root/'static.tar.gz'
            artifacts.pack_static(files,archive,1)
            self.assertEqual(artifacts.read_static(archive),files)

    def test_arbitrary_extensionless_vendor_files_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'dist/vendor/charts').mkdir(parents=True)
            (root/'dist/index.html').write_text('ok');(root/'dist/vendor/charts/OTHER').write_text('bad')
            with self.assertRaises(ValueError):artifacts.static_files(root)

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
            root=Path(tmp);(root/'MANIFEST.json').write_text(json.dumps({'schema':2,'commit':COMMIT,'files':{}}));(root/'SHA256SUMS').write_text('');(root/'private.env').write_text('bad')
            with self.assertRaises(ValueError):artifacts.verify(root,ROOT,COMMIT)

class SdistTests(unittest.TestCase):
    def fixture(self, root):
        theme = root / 'django-theme'
        (theme / 'src/nova_admin').mkdir(parents=True)
        (theme / 'pyproject.toml').write_text('[project]\nname="nova-django-admin-theme"\nversion="0.6.1"\nrequires-python=">=3.10"\nlicense="MIT"\n')
        for name in ('MANIFEST.in', 'LICENSE', 'requirements-test.txt', 'README.md', 'RELEASING.md'):
            (theme / name).write_text('source ' + name)
        (theme / 'src/nova_admin/__init__.py').write_text('__version__ = "0.6.1"\n')
        files = artifacts.sdist_files(root)
        info = b'Metadata-Version: 2.4\nName: nova-django-admin-theme\nVersion: 0.6.1\nRequires-Python: >=3.10\nLicense-Expression: MIT\nLicense-File: LICENSE\n\n'
        files.update({'PKG-INFO': info, 'setup.cfg': b''})
        egg = 'src/nova_django_admin_theme.egg-info/'
        files.update({egg + name: info if name == 'PKG-INFO' else b'' for name in
                      ('PKG-INFO', 'SOURCES.txt', 'dependency_links.txt', 'requires.txt', 'top_level.txt')})
        return files

    def write(self, root, files, extra=None):
        target = root / 'theme.tar.gz'
        with tarfile.open(target, 'w:gz') as archive:
            for name, content in files.items():
                item = tarfile.TarInfo('nova_django_admin_theme-0.6.1/' + name)
                item.size = len(content)
                archive.addfile(item, io.BytesIO(content))
            if extra:
                archive.addfile(extra)
        return target

    def test_complete_source_and_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = self.fixture(root)
            self.assertEqual(artifacts.sdist_check(self.write(root, files), root)['source_files'], 7)

    def json_fixture(self, root):
        files = self.fixture(root)
        name = 'tests/fixtures/brand-names.json'
        content = b'{"name": "Nova"}\n'
        path = root / 'django-theme' / name
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        files[name] = content
        return files

    def test_test_json_fixture_is_source_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = self.json_fixture(root)
            self.assertEqual(artifacts.sdist_check(self.write(root, files), root)['source_files'], 8)

    def test_missing_or_changed_test_json_fixture_refused(self):
        for change in ('missing', 'changed'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                files = self.json_fixture(root)
                name = 'tests/fixtures/brand-names.json'
                if change == 'missing': files.pop(name)
                else: files[name] = b'{"name": "tampered"}\n'
                with self.assertRaisesRegex(ValueError, 'source/documentation'):
                    artifacts.sdist_check(self.write(root, files), root)

    def test_unexpected_test_json_fixture_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = self.json_fixture(root)
            files['tests/fixtures/unexpected.json'] = b'{}'
            with self.assertRaisesRegex(ValueError, 'generated sdist content'):
                artifacts.sdist_check(self.write(root, files), root)

    def test_missing_or_changed_document_refused(self):
        for change in ('missing', 'changed'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                files = self.fixture(root)
                if change == 'missing': files.pop('RELEASING.md')
                else: files['RELEASING.md'] = b'stale upgrade guide'
                with self.assertRaisesRegex(ValueError, 'source/documentation'):
                    artifacts.sdist_check(self.write(root, files), root)

    def test_extra_secret_or_database_refused(self):
        for name in ('.env', 'demo/db.sqlite3', 'demo/unexpected.py'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                files = self.fixture(root)
                files[name] = b'not part of source'
                with self.assertRaises(ValueError): artifacts.sdist_check(self.write(root, files), root)

    def test_duplicate_link_and_traversal_refused(self):
        for name, kind in (('LICENSE', tarfile.REGTYPE), ('link', tarfile.SYMTYPE), ('../escape', tarfile.REGTYPE)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                files = self.fixture(root)
                item = tarfile.TarInfo('nova_django_admin_theme-0.6.1/' + name)
                item.type, item.linkname = kind, '/etc/passwd'
                with self.assertRaises(ValueError): artifacts.sdist_check(self.write(root, files, item), root)

    def test_wrong_license_metadata_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = self.fixture(root)
            files['PKG-INFO'] = files['PKG-INFO'].replace(b'MIT', b'BSD')
            with self.assertRaisesRegex(ValueError, 'license metadata'):
                artifacts.sdist_check(self.write(root, files), root)

if __name__=='__main__':unittest.main()
