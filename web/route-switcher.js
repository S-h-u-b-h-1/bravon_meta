(() => {
"use strict";
const routes=[
 {path:"/",label:"Workspace"},
 {path:"/#tour",label:"Proof Journey"},
 {path:"/muse",label:"Meta Muse"},
 {path:"/simulation",label:"Simulation"},
 {path:"/docker",label:"Docker · local only"},
 {path:"/assets/immortality.html",label:"Immortality"},
 {path:"/model-trials",label:"Model trials · sample"}
];
if(document.getElementById("bravon-route-switcher"))return;
const path=location.pathname.replace(/\/$/,"")||"/";
const nav=document.createElement("nav");
nav.id="bravon-route-switcher";
nav.className="bravon-route-switcher";
nav.setAttribute("aria-label","Switch Bravon labs");
const inner=document.createElement("div");inner.className="bravon-route-inner";
const brand=document.createElement("a");brand.href="/";brand.className="bravon-route-brand";brand.textContent="B / Bravon";brand.setAttribute("aria-label","Bravon workspace");
inner.appendChild(brand);
const links=document.createElement("div");links.className="bravon-route-links";
for(const route of routes){
 const a=document.createElement("a");a.href=route.path;a.textContent=route.label;
 if(route.path==="/#tour" ? path==="/" && location.hash==="#tour" : path===route.path && !(path==="/" && location.hash==="#tour")){a.setAttribute("aria-current","page");}
 links.appendChild(a);
}
inner.appendChild(links);nav.appendChild(inner);
const skip=document.querySelector(".skip-link");
if(skip && skip.parentElement===document.body){
  skip.insertAdjacentElement("afterend",nav);
}else{
  document.body.insertBefore(nav,document.body.firstChild);
}
})();