import tempfile
import unittest
from pathlib import Path

from perf import config, snapshot


class ConfigTests(unittest.TestCase):

    def test_dot_env_values_keep_dollar_signs_and_drop_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text('PERF_DB_PASSWORD="Meg$Rkm$Jd"\n# comment\nPERF_API_KEY=ak_1.secret\n\n', encoding="utf-8")
            values = config.read_properties(path)
        self.assertEqual(values["PERF_DB_PASSWORD"], "Meg$Rkm$Jd")
        self.assertEqual(values["PERF_API_KEY"], "ak_1.secret")

    def test_only_test_clusters_pass_verification(self):
        good = config.Config(env="recette", profile={"selfcare.baseUrl": "https://x.apps.ocpdev.attijariwafa.net", "orders.source": "PERF"}, secrets={})
        config.verify(good)
        bad = config.Config(env="prod", profile={"selfcare.baseUrl": "https://api.attijariwafa.net", "orders.source": "PERF"}, secrets={})
        with self.assertRaises(SystemExit):
            config.verify(bad)
        wrong_source = config.Config(env="recette", profile={"selfcare.baseUrl": "https://x.apps.ocpdev.attijariwafa.net", "orders.source": "MBK"}, secrets={})
        with self.assertRaises(SystemExit):
            config.verify(wrong_source)

    def test_campaign_id_rules(self):
        self.assertEqual(config.check_campaign_id("SMOKE-20261015A"), "SMOKE-20261015A")
        for bad in ("abc", "with space", "", "X" * 30):
            with self.assertRaises(SystemExit):
                config.check_campaign_id(bad)

    def test_committed_profiles_load(self):
        for env in ("recette", "preprod"):
            cfg = config.load(env)
            self.assertEqual(cfg.env, env)
            self.assertTrue(cfg.base_url.startswith("https://"))
            self.assertEqual(cfg.source, "PERF")


class SnapshotMaskTests(unittest.TestCase):

    def test_credentials_are_masked_in_yaml_and_properties(self):
        text = "MEGARA_DATABASE_PASSWORD: s3cret\nBROKER_LOGIN: ATI01\nmegacustody.credentials=user:pass\nserver.port=8080\n"
        masked = snapshot.mask(text)
        self.assertIn("MEGARA_DATABASE_PASSWORD: ***", masked)
        self.assertIn("megacustody.credentials= ***", masked)
        self.assertIn("BROKER_LOGIN: ATI01", masked)
        self.assertIn("server.port=8080", masked)
        self.assertNotIn("s3cret", masked)


if __name__ == "__main__":
    unittest.main()
