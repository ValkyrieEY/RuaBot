from src.core.startup_urls import append_url_path, build_startup_urls


def test_unspecified_host_prints_local_and_lan_urls():
    urls = build_startup_urls(
        "0.0.0.0",
        8000,
        lan_ips=["192.168.1.23"],
        public_ip="203.0.113.10",
    )

    assert [item.label for item in urls] == ["External", "Local", "LAN"]
    assert urls[0].url == "http://203.0.113.10:8000/"
    assert urls[1].url == "http://127.0.0.1:8000/"
    assert urls[2].url == "http://192.168.1.23:8000/"


def test_unspecified_host_omits_external_when_public_ip_not_detected():
    urls = build_startup_urls("0.0.0.0", 8000, lan_ips=[], public_ip="")

    assert [item.label for item in urls] == ["Local"]
    assert urls[0].url == "http://127.0.0.1:8000/"


def test_loopback_host_prints_local_only():
    urls = build_startup_urls("127.0.0.1", 8000, lan_ips=["192.168.1.23"])

    assert len(urls) == 1
    assert urls[0].label == "Local"
    assert urls[0].url == "http://127.0.0.1:8000/"


def test_append_url_path_normalizes_slashes():
    assert append_url_path("http://127.0.0.1:8000/", "/docs") == "http://127.0.0.1:8000/docs"
