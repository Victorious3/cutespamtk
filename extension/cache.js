let __cache = {}

function cache(url, result) {
    if (!result.img) return
    __cache[url] = result
    console.log("Caching", url, result)
}

function get_cached(url) {
    let cached = __cache[url]
    if (cached) console.log("Cache hit", url)
    else console.log("Cache miss", url)
    return cached
}

chrome.runtime.onMessage.addListener(
    function(request, sender, sendResponse) {
        if (request.msg == "cache") {
            cache(request.url, request.result)
        } else if (request.msg == "get-cached") {
            sendResponse(get_cached(request.url))
        }
    }
);

