async function handleUploadPfp(event) {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);

    try {
        const response = await fetch('/profile/upload', {
            method: 'POST',
            body: formData,
        });

        // Handle the server response
        if (response.ok) {
            const result = await response.json();
            if (result.status === 'ok') {
                alert(result.message || 'File uploaded successfully!');
                // Update the displayed profile picture if a new URL is returned
                if (result.profile_picture) {
                    const profileImg = document.getElementById('profilePicture');
                    if (profileImg) {
                        profileImg.src = result.profile_picture;
                    }
                }
                console.log(result); // Debugging or further logic
            } else {
                alert(result.message || 'Upload succeeded, but there was an issue.');
            }
        } else {
            const errorData = await response.json();
            alert(errorData.message || 'Failed to upload file.');
        }
    } catch (error) {
        console.error('Error during upload:', error);
        alert('An unexpected error occurred. Please try again.');
    }
}
