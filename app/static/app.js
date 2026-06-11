// Initialise drag-and-drop on every column's card list. Re-runs after HTMX swaps
// (e.g. when the board is re-rendered) so new lists become sortable too.
function initBoard() {
  document.querySelectorAll(".cards").forEach(function (el) {
    if (el._sortable) return;
    el._sortable = Sortable.create(el, {
      group: "videos",
      animation: 150,
      ghostClass: "drag-ghost",
      onEnd: function (evt) {
        var card = evt.item;
        var videoId = card.getAttribute("data-video-id");
        var columnId = evt.to.getAttribute("data-column-id");
        var body = new URLSearchParams();
        body.set("column_id", columnId);
        body.set("position", evt.newIndex);
        fetch("/videos/" + videoId + "/move", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: body.toString(),
        });
      },
    });
  });
}

document.addEventListener("DOMContentLoaded", initBoard);
document.body.addEventListener("htmx:afterSwap", initBoard);
