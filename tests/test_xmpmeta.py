
from pathlib import Path
from tempfile import TemporaryFile
from datetime import datetime
from uuid import UUID

from cutespam.xmpmeta import CuteMeta, Rating

TEST_XMP = Path("tests/data/test.xmp")
TEST_OUT = Path("tests/data/out.xmp")

def test_metadata():
    cm = CuteMeta(filename = TEST_OUT)
    cm.rating = Rating("q")
    cm.date = cm.last_updated = datetime.strptime("2017-05-29T00:00:59.412Z", "%Y-%m-%dT%H:%M:%S.%fZ")
    cm.hash = "b59f95ffc2e2f440ff006fb01a95c547ee163ee045c0c030ba3b570f4ecc28b5"
    cm.group_id = cm.uid = UUID("04a10461-a60b-4dc3-8d91-4a91b311f004")
    cm.source = "http://example.com/example_image.jpg"
    cm.author = "test_author"
    cm.source_other = cm.source_via = set(["http://example.com", "http://example.de"])
    cm.keywords = set(["test_keyword", "test_keyword_2"])
    cm.collections = set(["test_collection", "test_collection2", "test_collection3"])
    cm.caption = "Test Caption"
    cm.write()

    
    cm2 = CuteMeta(filename = TEST_OUT)
    cm2.read()

    cm3 = CuteMeta(filename = TEST_XMP)
    cm3.read()

    assert cm.as_dict() == cm2.as_dict() == cm3.as_dict()
    