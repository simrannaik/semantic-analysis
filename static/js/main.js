document.getElementById('searchForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const query = document.getElementById('queryInput').value;
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const submitButton = e.target.querySelector('button');
    
    // Disable the submit button
    submitButton.disabled = true;
    loading.classList.remove('hidden');
    results.classList.add('hidden');

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `query=${encodeURIComponent(query)}`
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'An error occurred');
        }

        // Update statistics
        const statsContent = document.getElementById('statsContent');
        statsContent.innerHTML = `
            <p>Total tweets analyzed: ${data.stats.total}</p>
            <p>Positive: ${data.stats.positive} (${((data.stats.positive/data.stats.total)*100).toFixed(1)}%)</p>
            <p>Negative: ${data.stats.negative} (${((data.stats.negative/data.stats.total)*100).toFixed(1)}%)</p>
            <p>Neutral: ${data.stats.neutral} (${((data.stats.neutral/data.stats.total)*100).toFixed(1)}%)</p>
        `;

        // Update tweets
        const tweetsContent = document.getElementById('tweetsContent');
        tweetsContent.innerHTML = data.results.map(tweet => `
            <div class="tweet">
                <p>${tweet.text}</p>
                <p class="sentiment-${tweet.sentiment}">Sentiment: ${tweet.sentiment}</p>
                <small>${tweet.created_at}</small>
            </div>
        `).join('');

        results.classList.remove('hidden');
    } catch (error) {
        alert(error.message);
        console.error(error);
    } finally {
        loading.classList.add('hidden');
        // Re-enable the submit button after 5 seconds
        setTimeout(() => {
            submitButton.disabled = false;
        }, 5000);
    }
});