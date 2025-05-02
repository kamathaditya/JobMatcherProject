document.getElementById('matcher-form').addEventListener('submit', async (e) => {
    e.preventDefault();
  
    // 1) Build FormData
    const form = e.target;
    const data = new FormData();
    data.append('role', form.role.value);
    data.append('description', form.description.value);
    data.append('qualifications', form.qualifications.value);
    data.append('preferences', form.preferences.value);
  
    // append each uploaded PDF
    const files = form.resumes.files;
    for (let i = 0; i < files.length; i++) {
      data.append('resumes', files[i], files[i].name);
    }
  
    // 2) Send to backend
    try {
      const resp = await fetch('/api/match', {
        method: 'POST',
        body: data
      });
  
      if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
  
      // 3) Parse JSON response
      //
      // Expect something like:
      // {
      //   "score": 87,
      //   "reason": "Close match on skills A, B, and C",
      //   "resumeUrl": "/downloads/best-candidate.pdf",
      //   "resumeName": "Alice_Smith.pdf"
      // }
      const result = await resp.json();
  
      // 4) Populate and show results
      document.getElementById('result-score').textContent = result.score;
      document.getElementById('result-reason').textContent = result.reason;
  
      const link = document.getElementById('result-resume-link');
      link.textContent = result.resumeName || 'Download';
      link.href = result.resumeUrl;
  
      document.getElementById('results').hidden = false;
  
    } catch (err) {
      alert('Something went wrong: ' + err.message);
    }
  });
  