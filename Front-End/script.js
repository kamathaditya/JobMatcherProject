/* Front-End/script.js
   Handles form submission, calls the FastAPI back‑end, and updates the page. */

   const form      = document.getElementById('job-form');
   const resultBox = document.getElementById('result');
   const errBox    = document.getElementById('error');
   const submitBtn = document.getElementById('submit-btn');
   
   // back‑end base URL – change if FastAPI isn’t on localhost:8000
   const API_BASE = 'http://localhost:8000';
   
   form.addEventListener('submit', async (e) => {
     e.preventDefault();
     errBox.hidden    = true;
     resultBox.hidden = true;
     submitBtn.disabled = true;
     submitBtn.textContent = 'Scoring…';
   
     try {
       // ── collect fields ──────────────────────────────────────────
       const data = new FormData(form);
       // add the selected PDF files
       const files = document.getElementById('resumes').files;
       for (const f of files) data.append('resumes', f);
   
       // ── POST to back‑end ───────────────────────────────────────
       const resp = await fetch(`${API_BASE}/api/match`, {
         method: 'POST',
         body: data,
       });
   
       if (!resp.ok) {
         throw new Error(`Server error ${resp.status}: ${await resp.text()}`);
       }
       const result = await resp.json();
   
       // ── render results ─────────────────────────────────────────
       document.getElementById('result-candidate').textContent = result.candidate;
       document.getElementById('result-score').textContent     = result.score;
       document.getElementById('result-reason').textContent    = result.reason;
       const link = document.getElementById('result-resume-link');
       link.textContent = `Download ${result.resumeName}`;
       link.href        = `${API_BASE}${result.resumeUrl}`;
   
       resultBox.hidden = false;
     } catch (err) {
       errBox.textContent = err.message;
       errBox.hidden = false;
     } finally {
       submitBtn.disabled = false;
       submitBtn.textContent = 'Find Best Match';
     }
   });
   