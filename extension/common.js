export let port = chrome.runtime.connectNative("moe.nightfall.booru")

port.onDisconnect.addListener(function(p) {
    let error = p.error || browser.runtime.lastError
    if (error) {
        console.log("Disconnected due to an error:", error.message);
    }
})

export async function request(json) {
    let promise = await new Promise((resolve, reject) => {
        let listener = function(message) {
            port.onMessage.removeListener(listener)
            console.log(message)
            resolve(message)
        }
        port.onMessage.addListener(listener)
        port.postMessage(json)
    }).catch(err => {throw err})
    return promise
}

export async function clear_image_cache() {
    await request({action: "clear-cache"})
}

export function cache(url, result) {
    chrome.runtime.sendMessage({msg: "cache", url: url, result: result})
}

export async function get_cached(url) {
    let promise = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({msg: "get-cached", url: url}, function(response) {
            resolve(response)
        })
    }).catch(err => {throw err})
    return promise
}


export async function fetch_url(url) {
    return await request({action: "fetch-url", url: url})
}
export async function iqdb_upscale(img, service, threshold = 0.9) {
    return await request({action: "iqdb-upscale", img: img, service: service, threshold: threshold})
}
export async function download_or_show_similar(data, threshold = 0.9) {
    return await request({action: "download-or-show-similar", data: data, threshold: threshold})
}

export async function XSS(tabid, fun) {
    let promise = await new Promise((resolve, reject) => {
        chrome.tabs.executeScript(tabid, {
            code: "(" + fun + ")();"
        }, function(res) { resolve(res[0]) })
    }).catch(err => {throw err})
    return promise
}

export function extract_twitter_url() {
    let gallery = document.querySelector(".gallery-overlay")
    computed = window.getComputedStyle(gallery)
    if (computed.display == "block") {
        // Curently viewing an image in the gallery
        image = document.querySelector(".Gallery-media img")
        return image.src
    } else {
        // Check if this is a post
        if (document.URL.indexOf("/post/")) {
            // Just return the url then
            return document.URL
        }
    }
    return null
}