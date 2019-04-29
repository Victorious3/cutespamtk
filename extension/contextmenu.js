chrome.contextMenus.create({
    title: "Import Image",
    id: "cutespam.import",
    contexts: ["image"],
});

chrome.contextMenus.onClicked.addListener(function(info, tab) {
    console.log(info)
    if (info.menuItemId == "cutespam.import") {
        chrome.windows.create({url: `import.html?popup=${encodeURIComponent(info.srcUrl)}&via=${encodeURIComponent(tab.url)}`, type: "popup", width: 400, height: 460});
    }
})