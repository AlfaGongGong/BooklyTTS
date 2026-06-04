import re
import json
import os


class NameReplacer:
    def __init__(self, profiles_dir='replacements'):
        self.profiles_dir = profiles_dir
        os.makedirs(profiles_dir, exist_ok=True)

    def _get_profile_file(self, epub_name=None):
        if epub_name and epub_name != '_global':
            safe = epub_name.replace('.epub', '').replace('/', '_')[:50]
            return f'{self.profiles_dir}/{safe}.json'
        return f'{self.profiles_dir}/_global.json'

    def get_rules(self, epub_name=None):
        rules = {}
        gf = self._get_profile_file(None)
        if os.path.exists(gf):
            with open(gf, 'r', encoding='utf-8') as f:
                rules.update(json.load(f))
        if epub_name and epub_name != '_global':
            bf = self._get_profile_file(epub_name)
            if os.path.exists(bf):
                with open(bf, 'r', encoding='utf-8') as f:
                    rules.update(json.load(f))
        return rules

    def add_rule(self, original, replacement, epub_name=None):
        pf = self._get_profile_file(
            epub_name if epub_name != '_global' else None)
        rules = {}
        if os.path.exists(pf):
            with open(pf, 'r', encoding='utf-8') as f:
                rules = json.load(f)
        rules[original] = replacement
        with open(pf, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)
        return self.get_rules(epub_name)

    def remove_rule(self, original, epub_name=None):
        pf = self._get_profile_file(
            epub_name if epub_name != '_global' else None)
        if os.path.exists(pf):
            with open(pf, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            if original in rules:
                del rules[original]
                with open(pf, 'w', encoding='utf-8') as f:
                    json.dump(rules, f, indent=2, ensure_ascii=False)
        return self.get_rules(epub_name)

    def apply(self, text, epub_name=None):
        rules = self.get_rules(epub_name)
        result = text
        for original, replacement in sorted(
                rules.items(), key=lambda x: -len(x[0])):
            result = re.sub(
                r'\b' + re.escape(original) + r'\b',
                replacement,
                result,
                flags=re.IGNORECASE
            )
        return result

    def list_profiles(self):
        profiles = []
        if not os.path.exists(self.profiles_dir):
            return profiles
        for f in os.listdir(self.profiles_dir):
            if f.endswith('.json'):
                name = f.replace('.json', '')
                with open(f'{self.profiles_dir}/{f}',
                          encoding='utf-8') as fh:
                    rules = json.load(fh)
                profiles.append({
                    'name': name,
                    'file': f,
                    'rule_count': len(rules),
                    'is_global': name == '_global'
                })
        return sorted(profiles, key=lambda x: not x['is_global'])

    def import_moonreader(self, text, epub_name=None):
        count = 0
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                parts = line.split('=', 1)
            elif '->' in line:
                parts = line.split('->', 1)
            else:
                continue
            if len(parts) == 2:
                orig = parts[0].strip().replace('#', '')
                repl = parts[1].strip().replace('#', '')
                if orig and repl:
                    self.add_rule(orig, repl, epub_name)
                    count += 1
        return {'count': count, 'rules': self.get_rules(epub_name)}

    def export_moonreader(self, epub_name=None):
        return '\n'.join(
            [f"{k}={v}" for k, v in self.get_rules(epub_name).items()])

    def merge_global_to_book(self, epub_name):
        global_rules = self.get_rules(None)
        for original, replacement in global_rules.items():
            self.add_rule(original, replacement, epub_name)
        return self.get_rules(epub_name)
