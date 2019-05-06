class argrange:
    def __init__(self, min, max):
        self.min = min
        self.max = max
    
    def __contains__(self, val):
        return self.min <= val <= self.max

    def __iter__(self):
        return iter([self.min, self.max])

def UUIDCompleter(prefix, **kwargs):
    from cutespam.db import get_tab_complete_uids
    completion = [str(uid) for uid in get_tab_complete_uids(prefix)]
    return completion

def UUIDFileCompleter(prefix, **kwargs):
    from argcomplete.completers import FilesCompleter
    completion = UUIDCompleter(prefix)
    if not completion:
        return FilesCompleter()(prefix)
    return completion