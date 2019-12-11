"use strict"

import * as common from "./common.js"

const MAX_HEIGHT = 650
const session = new common.Session()
let popup = false

let DATA = {
    img: null,
    service: null,
    url: null
}

function get_keywords(keyword_list) {
    return Array.from(keyword_list.querySelectorAll("li")).map(li => li.childNodes[0].nodeValue)
}

function get_list_elements(list) {
    return Array.from(list.childNodes).filter(c => c.nodeType == Node.TEXT_NODE).map(v => v.nodeValue)
}

function insert_keyword(keyword_list, keyword) {
    let ul = keyword_list.querySelector("ul")

    let all_keywods = get_keywords(keyword_list)
    if (all_keywods.includes(keyword)) return

    let li = document.createElement("li")
    let cross = document.createElement("span")
    cross.className = "cross"
    cross.innerText = "🗙"
    cross.addEventListener("click", function(event) {
        ul.removeChild(li)
    })

    li.appendChild(document.createTextNode(keyword))
    li.appendChild(cross)
    ul.insertBefore(li, ul.children[ul.children.length - 1])

    let label = keyword_list.querySelector("label")
    label.style.display = "none"
}

function update_data_fields(data) {
    if (data.img) {
        document.querySelector("#thumbnail").src = data.img
        document.querySelector("#source").value = data.img
    }
    if (data.caption) document.querySelector("textarea").value = data.caption
    if (data.rating) document.querySelector("#rating").value = data.rating
    if (data.author) document.querySelector("#author").value = data.author
    if (data.service) document.querySelector("#service").className = "service " + data.service
    if (data.uid) document.querySelector("#uid").value = data.uid

    if (data.keywords) {
        let keyword_list = document.querySelector("#keywords")
        for (let keyword of data.keywords) {
            insert_keyword(keyword_list, keyword)
        }  
    }
    if (data.character) {
        let character_list = document.querySelector("#characters")
        for (let character of data.character) {
            insert_keyword(character_list, character)
        }
    }
    if (data.collections) {
        let collection_list = document.querySelector("#collections")
        for (let collection of data.collections) {
            insert_keyword(collection_list, collection)
        }
    }

    if (data.src) {
        let src_list = document.querySelector("#add-source")
        src_list.innerHTML = ""
        for (let src of data.src) {
            src_list.appendChild(document.createTextNode(src))
            src_list.appendChild(document.createElement("br"))
        }
    }
    if (data.via) {
        let via_list = document.querySelector("#via")
        via_list.innerHTML = ""
        for (let via of data.via) {
            via_list.appendChild(document.createTextNode(via))
            via_list.appendChild(document.createElement("br"))
        }
    }


    /*if (response.iqdb) {
        document.querySelector("#iqdb-button").disabled = true
    }*/
}

function extract_data_fields() {
    let data = {...DATA}
    data.caption = document.querySelector("textarea").value
    data.rating = document.querySelector("#rating").value
    data.author = document.querySelector("#author").value
    data.keywords = get_keywords(document.querySelector("#keywords"))
    data.character = get_keywords(document.querySelector("#characters"))
    data.collections = get_keywords(document.querySelector("#collections"))
    data.src = get_list_elements(document.querySelector("#add-source"))
    data.via = get_list_elements(document.querySelector("#via"))
    return data
}

function update_cache() {
    common.cache(DATA.url, extract_data_fields())
}

window.addEventListener("blur", update_cache)

async function iqdb() {
    common.set_status("Fetching IQDB results", "loading")
    let reply = await common.iqdb_upscale(DATA.img, DATA.service)
    if (reply.error) {
        common.set_status(reply.error, "error")
        console.log(reply.error, reply.trace)
    } else {
        DATA = {...DATA, ...reply}
        DATA.iqdb = true // Reduce load
        common.cache(DATA.url, DATA)
        update_data_fields(reply)
        common.set_status("Found image!", "success")
        document.querySelector("#iqdb-button").disabled = true
    }
}

async function download() {
    DATA = extract_data_fields()
    common.set_status("Downloading file", "loading")
    let res = await common.download_or_show_similar(DATA)
    if (res != "OK") {
        session.set("DATA", DATA)  // Store in session for access from other page
        session.set("duplicates", res)
        window.location.replace("duplicates.html?popup=" + (popup ? "true": "false"))
    } else {
        if (res.error) {
            common.set_status(res.error, "error")
        } else {
            common.set_status("Added to collection", "success")
        }
    }
}

window.addEventListener("load", function() {
    document.querySelector("#iqdb-button").addEventListener("click", iqdb)
    document.querySelector("#download-button").addEventListener("click", download)

    function collapse() {
        let div = this.parentNode.querySelector("div")
        div.classList.toggle("collapsed")
    }
    for (let legend of document.querySelectorAll("legend")) {
        legend.addEventListener("click", collapse)
    }

    for (let autoresize of document.querySelectorAll(".autoresize span")) {
        autoresize.addEventListener("focus", function() { this.parentNode.classList.toggle("focus", true) })
        autoresize.addEventListener("blur", function() { this.parentNode.classList.toggle("focus", false) })
    }

    for (let keywords of document.querySelectorAll(".keywords")) {
        let span = keywords.querySelector("span")
        let ul = keywords.querySelector("ul")
        let default_text = keywords.querySelector("label")

        function add_last_keyword() {
            if (span.innerText.length > 0) {
                insert_keyword(keywords, span.innerText.trim())
                span.innerText = "" 
            }
        }

        span.addEventListener("focusout", function() {
            add_last_keyword()
            if (ul.children.length == 1) default_text.style.display = "initial"
        })
        span.addEventListener("focus", function() {
            default_text.style.display = "none"
        })
        keywords.addEventListener("click", function() {
            span.focus()
        })
        span.addEventListener("keydown", function(event) {
            if (event.code == "Backspace") {
                if (this.innerText == "" && ul.children.length > 1) {
                    ul.removeChild(ul.children[ul.children.length - 2])
                }
            } else if (event.code == "Space" || event.code == "Enter") {
                add_last_keyword()
                if (event.code == "Enter") {
                    span.blur()
                }
                event.preventDefault()
            }
        })
    }

    for (let element of document.querySelectorAll('*[contenteditable="true"]')) {
        element.addEventListener("paste", function(e) {
            e.preventDefault();
            var text = "";
            if (e.clipboardData && e.clipboardData.getData) {
                text = e.clipboardData.getData("text/plain");
            } else if (window.clipboardData && window.clipboardData.getData) {
                text = window.clipboardData.getData("Text");
            }
            document.execCommand("insertHTML", false, text);
        });
    }

    // update_cache()
})

window.addEventListener("load", async function() {
chrome.tabs.query({active: true, currentWindow: true}, async function(tabs) {

    common.set_status("Fetching metadata", "loading")

    let tab = tabs[0]
    let service = null

    let urlParams = new URLSearchParams(window.location.search)
    popup = urlParams.get("popup")

    if (popup) {
        // Using a different url
        DATA.url = decodeURIComponent(popup)
        DATA.via = [decodeURIComponent(urlParams.get("via"))]
        
        // resize yourself
        // TODO Fix resize
        /*let body = document.querySelector("body")
        let html = document.querySelector("html")
        html.style.overflow = "hidden"

        let auto_resized = false
        function onresize() {
            let v = 0 //body.offsetWidth - window.innerWidth + 20
            let h = body.offsetHeight - window.innerHeight

            if (window.innerHeight + h >= MAX_HEIGHT) {
                html.style.overflow = "initial"
                h = MAX_HEIGHT - window.innerHeight
            } else {
                html.style.overflow = "hidden"
            }
            
            window.resizeBy(v, h)
            auto_resized = true
        }
        onresize()
        let sensor = new ResizeSensor(body, onresize)

        // make sure to update cache on closing
        window.addEventListener("beforeunload", update_cache)

        window.addEventListener("resize", function() {
            if (!auto_resized) {
                sensor.detach(body)
                html.style.overflow = "initial"
            }
            auto_resized = false
        })*/
    } else {
        DATA.url = tab.url
        let url = new URL(DATA.url)

        if (url.hostname == "twitter.com") {
            service = "twitter"
            DATA.url = await common.XSS(tab.id, common.extract_twitter_url)
            if (!DATA.url) {
                chrome.pageAction.hide(tab.id); // Firefox
                return
            }
        }
    }
    
    let response = await common.get_cached(DATA.url) 
    if (!response) {
        response = await common.fetch_url(DATA.url)
        if (service) DATA.service = service
        if (!popup && tab.url != response.img) 
            DATA.via = [tab.url]
    }

    DATA = {...DATA, ...response}
    common.cache(DATA.url, DATA)
    update_data_fields(DATA)

    common.set_status()
})})