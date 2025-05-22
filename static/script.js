document.addEventListener('DOMContentLoaded', function() {
    // Tab switching functionality
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Remove active class from all buttons
            tabBtns.forEach(b => b.classList.remove('active'));
            // Add active class to clicked button
            this.classList.add('active');
            
            // Hide all tab contents
            tabContents.forEach(content => content.style.display = 'none');
            // Show the selected tab content
            const tabId = this.getAttribute('data-tab') + 'Tab';
            document.getElementById(tabId).style.display = 'block';
        });
    });
    
    // File upload functionality
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const urlBtn = document.getElementById('urlBtn');
    const videoUrlInput = document.getElementById('videoUrl');
    const resultsContainer = document.getElementById('resultsContainer');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const accentBadge = document.getElementById('accentBadge');
    const confidenceMeter = document.getElementById('confidenceMeter');
    const confidenceValue = document.getElementById('confidenceValue');
    const accentSummary = document.getElementById('accentSummary');
    const newAnalysisBtn = document.getElementById('newAnalysisBtn');
    
    let selectedFile = null;
    
    // Handle drag and drop events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        dropArea.classList.add('highlight');
    }
    
    function unhighlight() {
        dropArea.classList.remove('highlight');
    }
    
    // Handle file drop
    dropArea.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0 && files[0].type.startsWith('video/')) {
            handleFiles(files);
        }
    }
    
    // Handle file selection via browse button
    dropArea.addEventListener('click', () => {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            handleFiles(this.files);
        }
    });
    
    function handleFiles(files) {
        selectedFile = files[0];
        
        // Show file name in the drop area
        const fileName = selectedFile.name;
        dropArea.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="12" y1="18" x2="12" y2="12"></line>
                <line x1="9" y1="15" x2="15" y2="15"></line>
            </svg>
            <p>${fileName}</p>
            <span class="browse">Change file</span>
        `;
        
        // Enable upload button
        uploadBtn.disabled = false;
    }
    
    // Handle upload button click
    uploadBtn.addEventListener('click', uploadFile);
    
    function uploadFile() {
        if (!selectedFile) return;
        
        // Show loading state
        resultsContainer.style.display = 'block';
        loading.style.display = 'block';
        results.style.display = 'none';
        
        const formData = new FormData();
        formData.append('video', selectedFile);
        
        fetch('/detect-accent/', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            displayResults(data);
        })
        .catch(error => {
            console.error('Error:', error);
            accentSummary.textContent = 'An error occurred during analysis. Please try again.';
            loading.style.display = 'none';
            results.style.display = 'block';
        });
    }
    
    // Handle URL button click
    urlBtn.addEventListener('click', analyzeUrl);
    
    function analyzeUrl() {
        const url = videoUrlInput.value.trim();
        
        if (!url) {
            alert('Please enter a valid video URL');
            return;
        }
        
        // Show loading state
        resultsContainer.style.display = 'block';
        loading.style.display = 'block';
        results.style.display = 'none';
        
        fetch('/detect-accent-url/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: url })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            displayResults(data);
        })
        .catch(error => {
            console.error('Error:', error);
            accentSummary.textContent = 'An error occurred during analysis. Please try again.';
            loading.style.display = 'none';
            results.style.display = 'block';
        });
    }
    
    function displayResults(data) {
        // Hide loading, show results
        loading.style.display = 'none';
        results.style.display = 'block';
        
        // Update UI with results
        accentBadge.textContent = data.accent;
        
        // Set confidence meter
        const confidencePercent = Math.round(data.confidence * 100);
        confidenceMeter.style.width = `${confidencePercent}%`;
        confidenceValue.textContent = `${confidencePercent}%`;
        
        // Set color based on confidence
        if (confidencePercent >= 80) {
            confidenceMeter.style.background = 'linear-gradient(to right, #10b981, #059669)';
        } else if (confidencePercent >= 50) {
            confidenceMeter.style.background = 'linear-gradient(to right, #f59e0b, #d97706)';
        } else {
            confidenceMeter.style.background = 'linear-gradient(to right, #ef4444, #dc2626)';
        }
        
        // Set summary
        accentSummary.textContent = data.summary;
    }
    
    // Handle "Analyze Another Video" button
    newAnalysisBtn.addEventListener('click', function() {
        // Reset UI
        resultsContainer.style.display = 'none';
        
        // Reset file upload UI
        dropArea.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <p>Drag & drop your video here or <span class="browse">browse</span></p>
        `;
        uploadBtn.disabled = true;
        selectedFile = null;
        
        // Reset URL input
        videoUrlInput.value = '';
    });
});