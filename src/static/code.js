document.addEventListener('DOMContentLoaded', () => {
    if (Post) {PostStuff()};
});
shortenText();
function shortenText() {
  const maxLength = 80; // number of characters to show initially
  posts = document.querySelectorAll('.post-text');

  posts.forEach(post => {
    post.style.display = 'block'; // makes it visible
    const fullText = post.textContent.trim();

    if (fullText.length > maxLength) {
      const shortText = fullText.slice(0, maxLength) + '...';

      // Create elements
      const shortSpan = document.createElement('span');
      shortSpan.className = 'short-text';
      shortSpan.textContent = shortText;

      const fullSpan = document.createElement('span');
      fullSpan.className = 'full-text';
      fullSpan.textContent = fullText;
      fullSpan.style.display = 'none';

      const readMore = document.createElement('span');
      readMore.className = 'read-more';
      readMore.textContent = '\n[Read More]';
      readMore.style.color = "blue";
	  readMore.style.cursor = "pointer";
	  readMore.addEventListener("mouseover", () => {
	    readMore.style.textDecoration = "underline";
	  });
	  readMore.addEventListener("mouseout", () => {
	    readMore.style.textDecoration = "none";
	  });
    readMore.style.fontStyle = 'italic';
      readMore.addEventListener('click', () => {
        if (fullSpan.style.display === 'none') {
          fullSpan.style.display = 'inline';
          shortSpan.style.display = 'none';
          readMore.textContent = ' [Read Less]';
        } else {
          fullSpan.style.display = 'none';
          shortSpan.style.display = 'inline';
          readMore.textContent = '\n[Read More]';
        }
		
      });

      // Clear original text and append new elements
      post.textContent = '';
      post.appendChild(shortSpan);
      post.appendChild(fullSpan);
      post.appendChild(readMore);
    }
  });
}
function PostStuff(){
        const updateCounts = (postId, likeCount, dislikeCount) => {
            document.getElementById(`like-count-${postId}`).textContent = likeCount;
            document.getElementById(`dislike-count-${postId}`).textContent = dislikeCount;
        };

        document.querySelectorAll('.like-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const postId = btn.getAttribute('data-id');
                const res = await fetch(`/like/${postId}`, { method: 'POST' });
                const data = await res.json();
                if (data.success) updateCounts(postId, data.like_count, data.dislike_count);
            });
        });

        document.querySelectorAll('.dislike-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const postId = btn.getAttribute('data-id');
                const res = await fetch(`/dislike/${postId}`, { method: 'POST' });
                const data = await res.json();
                if (data.success) updateCounts(postId, data.like_count, data.dislike_count);
            });
        });
    /**
     * Front-end "time ago" updater for elements with class="timestamp".
     * - Supports formats: "YYYY-MM-DD HH:MM:SS",   "YYYY-MM-DDTHH:MM:SS(.sss)(Z|±hh:mm)", or numeric epoch.
     * - If your server timestamps are in UTC but lack a 'Z', set assumeUTC =   true (see note).
     */
}
const assumeUTC = true; // <-- set true if your server timestamps are UTC    but have no timezone marker
function parseTimestamp(ts) {
  if (!ts) return null;
  // If it's a number (epoch seconds or ms)
  if (!isNaN(ts)) {
    // use numeric value; try to decide seconds vs ms (>=1e12 => ms)
    const n = Number(ts);
    return n > 1e12 ? new Date(n) : new Date(n * 1000);
  }
  // Trim and normalize
  ts = String(ts).trim();
  // If it's like "YYYY-MM-DD HH:MM:SS" -> convert to "YYYY-MM-DDTHH:MM:SS"
  // Browsers reliably parse "YYYY-MM-DDTHH:MM:SS" as local time, and     "YYYY-MM-DDTHH:MM:SSZ" as UTC.
  const spaceDateTime = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?$/;
  if (spaceDateTime.test(ts)) {
    let iso = ts.replace(' ', 'T');
    if (assumeUTC) iso += 'Z';
    return new Date(iso);
  }
  // If it's ISO-ish but missing Z and you want to assume UTC, add Z
  const isoNoTZ = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/;
  if (isoNoTZ.test(ts) && assumeUTC) {
    return new Date(ts + 'Z');
  }
  // Otherwise let Date try to parse (handles ISO with timezone)
  const d = new Date(ts);
  return isNaN(d.getTime()) ? null : d;
}
function timeAgo(date, now = new Date()) {
  if (!date) return '';
  let seconds = Math.floor((now - date) / 1000);
  if (seconds < 0) seconds = 0;
  if (seconds < 10) return 'just now';
  if (seconds < 60) return `${seconds} second${seconds !== 1 ? 's' : ''}  ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min${minutes !== 1 ? 's' : ''} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} day${days !== 1 ? 's' : ''} ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} month${months !== 1 ? 's' : ''} ago`;
  const years = Math.floor(months / 12);
  return `${years} year${years !== 1 ? 's' : ''} ago`;
}
function updateTimestamps() {
  const nodes = document.querySelectorAll('.timestamp');
  const now = new Date();
  nodes.forEach(node => {
    // Save original raw value in data-original if not already set
    if (!node.dataset.original) node.dataset.original = node.textContent. trim();
    const raw = node.dataset.original;
    const dt = parseTimestamp(raw);
    const pretty = dt ? timeAgo(dt, now) : raw; // fall back to raw if    parse fails
    node.textContent = pretty;
    // keep full timestamp visible on hover
    node.title = raw;
  });
}
// initial run
updateTimestamps();	// refresh every 60 seconds so "mins ago" stays accurate
setInterval(updateTimestamps, 60 * 1000);

function ChangeDescription(){
  di = document.getElementById('description_input');
  dc = document.getElementById('description_cancel');
  db = document.getElementById('description_button');

  if (db.innerHTML == "Apply Changes"){
    ApplyChanges();
  }
  di.style.display = "inline";
  dc.style.display = "inline";
  db.innerHTML = "Apply Changes"
  di.focus();
}
function CancelDescription() {
  di = document.getElementById('description_input');
  dc = document.getElementById('description_cancel');
  db = document.getElementById('description_button');

  db.innerHTML = "Change Description"
  di.style.display = "none";
  dc.style.display = "none";
}
async function ApplyChanges() {
    const desc = document.getElementById("description_input").value;
    try {
        let response = await fetch("/description", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ description: desc })
        });

        if (response.ok) {
            const data = await response.json();
            document.querySelector("body > main > div.card.profile-header > h4").textContent = desc;
        } else {
            alert("Failed to update description.");
        }
    } catch (err) {
        console.error("Error:", err);
        alert("Something went wrong.");
    }
}
// to simulate a click !!!
document.querySelector("body > main > div.card.profile-header > h4").addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
        event.preventDefault(); // stop form submission if inside a form
        document.getElementById("description_button").click(); // trigger the click
    }
});
// deleting a post
function deletePost(postId, shouldConfirm = true) {
  if (shouldConfirm) {
    if (!confirm("Do you want to continue with deleting this post? (This cannot be undone)")) {
      return; // user canceled
    }
  }

  // Create a form dynamically to send POST request
  const form = document.createElement("form");
  form.method = "POST";
  form.action = `/delete/${postId}`;  // matches your backend route

  document.body.appendChild(form);
  form.submit();
}
