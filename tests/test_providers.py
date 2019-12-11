from cutespam.providers import TwitterStatus

def test_twitter_status():
    url = "https://twitter.com/lalamlou/status/1204624146904207362/photo/2"
    status = TwitterStatus(url)
    status._fetch()
    assert status.src[0] == "https://pbs.twimg.com/media/ELevQ-iUEAEi8Fm.jpg"