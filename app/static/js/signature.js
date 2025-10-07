// Firma simple sin dependencias.
// Exponer un objeto global SIG con open/clear/toDataURL/close.

(function(){
  const SIG = {};
  let canvas, ctx;
  let drawing = false;
  let last = null;
  let listenersBound = false;

  function sizeCanvas(){
    if (!canvas) return;
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;
    ctx.scale(ratio, ratio);
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#000";
  }

  function getPos(e){
    if (e.touches && e.touches.length) {
      const t = e.touches[0];
      const rect = canvas.getBoundingClientRect();
      return { x: t.clientX - rect.left, y: t.clientY - rect.top };
    } else {
      const rect = canvas.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }
  }

  function onDown(e){
    e.preventDefault();
    drawing = true;
    last = getPos(e);
  }
  function onMove(e){
    if (!drawing) return;
    const p = getPos(e);
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last = p;
  }
  function onUp(e){
    drawing = false;
    last = null;
  }

  function bind(){
    if (listenersBound) return;
    canvas.addEventListener("mousedown", onDown);
    canvas.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    canvas.addEventListener("touchstart", onDown, {passive:false});
    canvas.addEventListener("touchmove", onMove, {passive:false});
    window.addEventListener("touchend", onUp);
    listenersBound = true;
  }
  function unbind(){
    if (!listenersBound) return;
    canvas.removeEventListener("mousedown", onDown);
    canvas.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
    canvas.removeEventListener("touchstart", onDown);
    canvas.removeEventListener("touchmove", onMove);
    window.removeEventListener("touchend", onUp);
    listenersBound = false;
  }

  SIG.open = function(){
    canvas = document.getElementById("sig-canvas");
    if (!canvas) return;
    ctx = canvas.getContext("2d");
    sizeCanvas();
    ctx.fillStyle = "transparent";
    ctx.clearRect(0,0,canvas.width, canvas.height);
    bind();
    window.addEventListener("resize", sizeCanvas);
  };

  SIG.clear = function(){
    if (!ctx || !canvas) return;
    ctx.clearRect(0,0,canvas.width, canvas.height);
  };

  SIG.toDataURL = function(){
    if (!canvas) return "";
    return canvas.toDataURL("image/png");
  };

  SIG.close = function(){
    unbind();
    window.removeEventListener("resize", sizeCanvas);
  };

  window.SIG = SIG;
})();
