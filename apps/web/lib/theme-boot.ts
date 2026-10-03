const SKIN_KEY = "ata-skin";
const MODE_KEY = "ata-mode";
const DEFAULT_KEY = "ata-skin-default";

/** Runs before first paint (inlined in <head>) so the stored look applies without a flash. */
export const THEME_BOOT_SCRIPT = `(function(){try{var d=document.documentElement;var s=localStorage.getItem("${SKIN_KEY}")||localStorage.getItem("${DEFAULT_KEY}");if(s!=="classic")d.setAttribute("data-skin","forest");var m=localStorage.getItem("${MODE_KEY}");if(m==="light"||m==="dark")d.setAttribute("data-theme",m);}catch(e){}})();`;
