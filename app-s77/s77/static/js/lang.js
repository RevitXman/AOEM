function switchLang(e){
  const v = e.target.value || "en";
  document.cookie = "lang="+v+"; path=/; max-age="+(60*60*24*365);
  window.location.reload();
}
