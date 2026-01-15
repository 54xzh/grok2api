import unittest


class TestClashHysteria2Parsing(unittest.TestCase):
    def test_parse_hysteria2_uri_maps_fingerprint_to_client_fingerprint(self) -> None:
        from app.services.clash import ClashManager

        cm = ClashManager.get_instance()
        proxy = cm._parse_hysteria2_uri(
            "hysteria2://example.com:443?auth=abc&fingerprint=chrome&sni=example.com#test"
        )
        self.assertIsInstance(proxy, dict)
        assert proxy is not None

        self.assertEqual(proxy.get("type"), "hysteria2")
        self.assertEqual(proxy.get("client-fingerprint"), "chrome")
        self.assertNotIn("fingerprint", proxy)

    def test_parse_hysteria2_uri_accepts_auth_str(self) -> None:
        from app.services.clash import ClashManager

        cm = ClashManager.get_instance()
        proxy = cm._parse_hysteria2_uri("hy2://example.com:443?auth_str=abc#test")
        self.assertIsInstance(proxy, dict)
        assert proxy is not None
        self.assertEqual(proxy.get("password"), "abc")

    def test_normalize_proxy_moves_non_hex_fingerprint(self) -> None:
        from app.services.clash import ClashManager

        cm = ClashManager.get_instance()
        proxy = {"name": "a", "type": "hysteria2", "fingerprint": "chrome"}
        cm._normalize_proxy_fields(proxy)
        self.assertEqual(proxy.get("client-fingerprint"), "chrome")
        self.assertNotIn("fingerprint", proxy)

    def test_normalize_proxy_keeps_hex_fingerprint(self) -> None:
        from app.services.clash import ClashManager

        cm = ClashManager.get_instance()
        fp = "a" * 64
        proxy = {"name": "a", "type": "hysteria2", "fingerprint": fp}
        cm._normalize_proxy_fields(proxy)
        self.assertEqual(proxy.get("fingerprint"), fp)
        self.assertNotIn("client-fingerprint", proxy)


if __name__ == "__main__":
    unittest.main()

