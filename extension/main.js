"use strict"

async function clear_cache() {
    const common = await import("./common.js")
    common.clear_image_cache()
}
clear_cache()

let matchers = [
    ".*twitter.com/.*/status/.*",
    ".*danbooru.donmai.us/posts/([\\d]+)",
    ".*safebooru.org/.*s=view.*",
    ".*zerochan.net/(full/)?([\\d]+)",
    ".*e-shuushuu.net/image/([\\d]+)"
]

chrome.runtime.onInstalled.addListener(function() {
    if (chrome.declarativeContent) {
        chrome.declarativeContent.onPageChanged.removeRules(undefined, function() {
            chrome.declarativeContent.onPageChanged.addRules([{
                conditions: [
                    new chrome.declarativeContent.PageStateMatcher({
                        pageUrl: { hostEquals: "twitter.com" },
                        css: [".gallery-overlay"]
                    }),
                    new chrome.declarativeContent.PageStateMatcher({
                        pageUrl: { pathSuffix: ".jpg"}
                    }),
                    new chrome.declarativeContent.PageStateMatcher({
                        pageUrl: { pathSuffix: ".jpeg"}
                    }),
                    new chrome.declarativeContent.PageStateMatcher({
                        pageUrl: { pathSuffix: ".png"}
                    })
                ].concat(matchers.map(m => new chrome.declarativeContent.PageStateMatcher({pageUrl: { urlMatches: m }}))),
                actions: [new chrome.declarativeContent.ShowPageAction()]
            }])
        })
    }
})

if (!chrome.declarativeContent) {
    chrome.tabs.onUpdated.addListener(function(tabId, changeInfo, tab) {
        let url = new URL(tab.url)
        if (matchers.map(m => url.href.match(m)).some(m => m) || url.hostname.match("twitter.com") || url.pathname.match("\\.(jpg|jpeg|png)$")) {
            chrome.pageAction.show(tabId);
        } else {
            chrome.pageAction.hide(tabId);
        }
    })
}