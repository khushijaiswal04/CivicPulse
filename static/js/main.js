// Small client-side enhancements for CivicPulse.
document.addEventListener("DOMContentLoaded", () => {
  // Prevent accidental double-submission on forms with a submit button.
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector('button[type="submit"], button:not([type])');
      if (button) {
        button.dataset.originalText = button.textContent;
        button.textContent = "Please wait...";
        button.disabled = true;
      }
    });
  });
});

// =====================================
// CIVICPULSE SMART CATEGORY SUGGESTION
// =====================================

document.addEventListener("DOMContentLoaded", function () {

      const suggestButton =
          document.getElementById("suggestCategory");

      const categorySelect =
          document.getElementById("category");

      const descriptionInput =
          document.querySelector('textarea[name="description"]');

      const titleInput =
          document.querySelector('input[name="title"]');

      const resultBox =
          document.getElementById("categorySuggestion");

      if (!suggestButton || !categorySelect ||
          !descriptionInput || !resultBox) {
          return;
      }

      const keywords = {

          "Road": [
              "road", "pothole", "street damage",
              "broken road", "footpath", "traffic",
              "crack", "road repair"
          ],

          "Water Supply": [
              "water", "water supply", "no water",
              "leakage", "pipe leak", "tap",
              "drinking water", "shortage"
          ],

          "Electricity": [
              "electricity", "power cut", "street light",
              "light not working", "electric pole",
              "wire", "transformer", "electric"
          ],

          "Garbage": [
              "garbage", "trash", "waste",
              "dustbin", "dirty", "cleaning",
              "rubbish", "sanitation"
          ],

          "Drainage": [
              "drain", "drainage", "sewer",
              "overflow", "sewage", "blocked drain",
              "waterlogging", "dirty water"
          ],

          "Public Safety": [
              "accident", "unsafe", "crime",
              "broken manhole", "danger",
              "open manhole", "street safety"
          ]

      };

      suggestButton.addEventListener("click", function () {

          const text = (
              (titleInput ? titleInput.value : "") + " " +
              descriptionInput.value
          ).toLowerCase().trim();

          if (!text) {
              resultBox.textContent =
                  "Please enter a complaint title or description first.";
              return;
          }

          const scores = {};

          Object.entries(keywords).forEach(
              ([category, words]) => {

                  scores[category] = 0;

                  words.forEach(word => {

                      const escaped = word.replace(
                          /[.*+?^${}()|[\]\\]/g, "\\$&"
                      );

                      const regex = new RegExp(
                          "\\b" + escaped + "\\b", "g"
                      );

                      const matches = text.match(regex);

                      if (matches) {
                          scores[category] += matches.length;
                      }

                  });

              }
          );

          const maxScore = Math.max(...Object.values(scores));

          if (maxScore === 0) {
              resultBox.textContent =
                  "No clear category found. Please select a category manually.";
              return;
          }

          const matches = Object.keys(scores).filter(
              category => scores[category] === maxScore
          );

          if (matches.length > 1) {
              resultBox.textContent =
                  "Multiple categories may match. Please select manually.";
              return;
          }

          const suggestedCategory = matches[0];

          categorySelect.value = suggestedCategory;

          resultBox.textContent =
              "Suggested Category: " + suggestedCategory +
              " — You can change it before submitting.";

  });
});
