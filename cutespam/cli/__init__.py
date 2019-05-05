def UUIDCompleter(prefix, **kwargs):
    from argcomplete.completers import FilesCompleter
    from cutespam.db import get_tab_complete_uids

    completion = [str(uid) for uid in get_tab_complete_uids(prefix)]
    if not completion:
        return FilesCompleter()(prefix)
    return completion