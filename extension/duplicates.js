"use strict"

import * as common from "./common.js"

const session = new common.Session()
let DATA = session.get("DATA")

let urlParams = new URLSearchParams(window.location.search)
let popup = urlParams.get("popup") == "true"

async function download() {
    common.set_status("Downloading file", "loading")
    let res = await common.download(DATA)

    if (res.error) {
        common.set_status(res.error, "error")
    } else {
        common.set_status("Added to collection", "success")
    }
}

window.addEventListener("load", function() {
    document.querySelector("#download-button").addEventListener("click", download)
    
    let body = document.querySelector("body")
    let html = document.querySelector("html")

    common.set_status("Found potential duplicates. Proceed?", "error")
    document.querySelector("#thumbnail").src = DATA.img
    
    let images = document.querySelector("#images")
    let duplicates = session.get("duplicates")
    for (let duplicate of duplicates) {
        let src = "image/" + duplicate.file

        let a = document.createElement("a") 
        a.href = src
        a.target = "_blank"
        
        let img = document.createElement("img")
        img.classList.add("duplicate")
        img.src = src
        img.title = (duplicate.similarity * 100).toFixed(1) + "%"

        a.appendChild(img)
        images.appendChild(a)
    }

    if (!popup) {
        let content = document.querySelector(".content")
        function on_resize() {
            if (images.offsetHeight > 160) {
                if (images.offsetHeight > 540) {
                    body.style["height"] = "600px"
                } else {
                    body.style["height"] = "initial"
                    html.style["height"] = "initial"
                    content.style["overflow"] = "inherit"
                }
            } else {
                window.requestAnimationFrame(on_resize)
            }
        }
        on_resize()
    }
})