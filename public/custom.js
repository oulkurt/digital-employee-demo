/**
 * Custom JavaScript for Chainlit UI
 * Skip the "Create New Chat" confirmation dialog
 */

(function() {
  'use strict';

  // Wait for DOM to be ready
  function init() {
    // Use MutationObserver to detect when the dialog appears
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        mutation.addedNodes.forEach(function(node) {
          if (node.nodeType === Node.ELEMENT_NODE) {
            // Check if this is the new chat confirmation dialog
            const dialogTitle = node.querySelector && node.querySelector('[id="side-view-title"], [role="alertdialog"] h2, [role="dialog"] h2');
            if (dialogTitle) {
              const titleText = dialogTitle.textContent || '';
              // Match both English and Chinese titles
              if (titleText.includes('Create New Chat') || titleText.includes('新对话') || titleText.includes('创建新对话')) {
                // Find and click the Confirm button
                const confirmBtn = node.querySelector('button:not([data-variant="ghost"]):not([aria-label])');
                const buttons = node.querySelectorAll('button');
                buttons.forEach(function(btn) {
                  const btnText = btn.textContent || '';
                  if (btnText.includes('Confirm') || btnText.includes('确认') || btnText.includes('确定')) {
                    // Auto-click confirm after a short delay
                    setTimeout(function() {
                      btn.click();
                    }, 50);
                  }
                });
              }
            }
          }
        });
      });
    });

    // Start observing the document body for added nodes
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
