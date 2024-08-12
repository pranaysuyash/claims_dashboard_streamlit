document.addEventListener("DOMContentLoaded", function () {
  const fileInput = document.getElementById("file-input");
  const analyzeBtn = document.getElementById("analyze-btn");

  analyzeBtn.addEventListener("click", function () {
    const file = fileInput.files[0];
    if (file) {
      const formData = new FormData();
      formData.append("file", file);

      fetch("/upload", {
        method: "POST",
        body: formData,
      })
        .then((response) => {
          if (!response.ok) {
            return response.json().then((err) => {
              throw new Error(err.error);
            });
          }
          return response.json();
        })
        .then((data) => {
          displayResults(data);
        })
        .catch((error) => {
          console.error("Error:", error);
          alert(error.message);
        });
    }
  });
});

function displayPivotTable(elementId, tableHtml, hierarchyData, columnNames) {
  console.log("displayPivotTable called with:", {
    elementId,
    tableHtml: tableHtml.substring(0, 100) + "...",
    hierarchyData: Object.keys(hierarchyData),
    columnNames,
  });

  const element = document.getElementById(elementId);
  if (!element) {
    console.error(`Element with id "${elementId}" not found`);
    return;
  }

  // 1. Create a new table element
  const table = document.createElement("table");
  table.classList.add("display", "responsive", "nowrap");
  table.id = "pivot_claims";

  // 2. Create table header
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  const expandHeader = document.createElement("th");
  expandHeader.textContent = "";
  headerRow.appendChild(expandHeader);

  // Only add 'hospital_name' to the main table header
  const hospitalNameHeader = document.createElement("th");
  hospitalNameHeader.textContent = "hospital_name";
  headerRow.appendChild(hospitalNameHeader);

  thead.appendChild(headerRow);
  table.appendChild(thead);

  // 3. Create table body
  const tbody = document.createElement("tbody");
  table.appendChild(tbody);

  // 4. Append the new table to the target element
  element.innerHTML = "";
  element.appendChild(table);

  try {
    const $table = $(`#${elementId} table`);
    console.log("Table element:", $table.length ? "Found" : "Not found");

    // 5. Prepare DataTables data (corrected)
    const tableData = Object.entries(hierarchyData).map(
      ([hospital, categories]) => ({
        expand: "",
        hospital_name: hospital,
        ...categories,
      })
    );

    // 6. Initialize DataTable (corrected)
    const dataTable = $table.DataTable({
      pageLength: 10,
      lengthMenu: [
        [10, 25, 50, -1],
        [10, 25, 50, "All"],
      ],
      responsive: true,
      columns: [
        {
          data: "expand",
          defaultContent: '<span class="expand-btn">+</span>',
          orderable: false,
          className: "details-control",
        },
        { data: "hospital_name", title: "Hospital Name" }, // Only hospital_name column
      ],
      data: tableData,
      order: [[1, "asc"]], // Sort by hospital name
    });

    console.log("DataTable initialized successfully");

    // 7. Event listener for expanding/collapsing rows
    $table.on("click", "td.details-control", function () {
      const tr = $(this).closest("tr");
      const row = dataTable.row(tr);
      console.log("Row clicked:", row.index());

      if (row.child.isShown()) {
        row.child.hide();
        tr.removeClass("shown");
        $(this).html('<span class="expand-btn">+</span>');
      } else {
        const hospitalName = row.data().hospital_name; // Direct access
        console.log("Hospital name:", hospitalName);

        if (hospitalName && hierarchyData[hospitalName]) {
          const categories = hierarchyData[hospitalName];
          console.log("Categories for hospital:", categories);

          // Create the child table HTML here
          let childContent =
            '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">';
          for (const [category, value] of Object.entries(categories)) {
            // Only display categories with non-zero values
            if (value > 0) {
              childContent += `<tr><td>${category}</td><td>${value.toFixed(
                2
              )}</td></tr>`;
            }
          }
          childContent += "</table>";

          row.child(childContent).show();
          tr.addClass("shown");
          $(this).html('<span class="expand-btn">-</span>');
        } else {
          row.child("No data available for this hospital").show();
          tr.addClass("shown");
          $(this).html('<span class="expand-btn">-</span>');
        }
      }
    });
  } catch (error) {
    console.error("Error initializing DataTable:", error);
    console.error("Error stack:", error.stack);
  }
}
function displayResults(data) {
  // Display charts
  displayChart("age-distribution", data.charts.age_distribution);
  displayChart("amount-paid-vs-age", data.charts.amount_paid_vs_age);
  displayChart("monthly-claims-trend", data.charts.monthly_claims_trend);
  displayChart("daily-claims", data.charts.daily_claims);
  displayChart("weekly-claim-creation", data.charts.weekly_claim_creation);
  displayChart("weekly-admission", data.charts.weekly_admission);
  displayChart("weekly-discharge", data.charts.weekly_discharge);
  displayChart("monthly-claim-creation", data.charts.monthly_claim_creation);
  displayChart("monthly-admission", data.charts.monthly_admission);
  displayChart("monthly-discharge", data.charts.monthly_discharge);
  displayDiseaseCategories(
    data.data.disease_category_counts,
    data.charts.disease_category_distribution
  );

  // Display tables
  displayTable("descriptive-stats", data.tables.descriptive_stats);
  displayTable("disease-freq", data.tables.disease_freq);
  displayTable("hospital-freq", data.tables.hospital_freq);
  displayTable("city-freq", data.tables.city_freq);
  displayTable("pivot-claims", data.tables.pivot_claims);
  displayTable("mean-paid-by-disease", data.tables.mean_paid_by_disease);
  displayTable("total-claim-by-city", data.tables.total_claim_by_city);
  displayTable("disease-category-stats", data.tables.disease_category_stats);

  // Display statistics
  displayHypothesisTest(data.statistics.hypothesis_test);

  // Handle the pivot table separately
  displayPivotTable(
    "pivot-claims",
    data.tables.pivot_claims,
    data.data.pivot_claims,
    data.data.pivot_claims_columns
  );
  // Display disease tests table
  if (data.tables && data.tables.disease_tests) {
    console.log("Received disease tests table data");
    displayTable("disease-tests", data.tables.disease_tests);
} else {
    console.error("No disease tests table data received");
}
}

function displayChart(elementId, chartData) {
  const element = document.getElementById(elementId);
  element.innerHTML = `<img src="data:image/png;base64,${chartData}" alt="${elementId} chart">`;
}

function displayTable(elementId, tableHtml) {
  console.log(`Displaying table for ${elementId}`);
  const element = document.getElementById(elementId);
  // element.innerHTML = tableHtml;
  if (element) {
    element.innerHTML = tableHtml;
    console.log(`Table HTML set for ${elementId}`);


  // Initialize DataTable
  try{
    $(`#${elementId} table`).DataTable({
    pageLength: 10,
    lengthMenu: [
      [10, 25, 50, -1],
      [10, 25, 50, "All"],
    ],
    responsive: true,
    dom: "Bfrtip",
    buttons: ["copy", "csv", "excel", "pdf", "print"],
  });
  console.log(`DataTable initialized for ${elementId}`);
  } catch (error) {
    console.error(`Error initializing DataTable for ${elementId}:`, error);
  }
  } else {
    console.error(`Element ${elementId} not found`);
  }
}

function displayDiseaseCategories(data, chartData) {
  const element = document.getElementById("disease-category-distribution");
  if (!element) {
    console.error("Element 'disease-category-distribution' not found");
    return;
  }
  element.innerHTML = `
        <select id="category-select">
            <option value="5">Top 5</option>
            <option value="10">Top 10</option>
            <option value="all">All</option>
            <option value="custom">Custom</option>
        </select>
        <input type="number" id="custom-top" min="1" max="${data.length}" style="display:none;">
        <img src="data:image/png;base64,${chartData}" alt="Disease Category Distribution">
    `;

  const select = document.getElementById("category-select");
  const customInput = document.getElementById("custom-top");

  if (select && customInput) {
    select.addEventListener("change", function () {
      if (this.value === "custom") {
        customInput.style.display = "inline";
      } else {
        customInput.style.display = "none";
        updateChart(this.value === "all" ? data.length : parseInt(this.value));
      }
    });

    customInput.addEventListener("change", function () {
      updateChart(parseInt(this.value));
    });
  } else {
    console.error("Select or custom input element not found");
    return;
  }

  function updateChart(topN) {
    const filteredData = data.slice(0, topN);
    fetch("/update_disease_chart", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ data: filteredData }),
    })
      .then((response) => response.json())
      .then((newChartData) => {
        const img = element.querySelector("img");
        if (img) {
          img.src = `data:image/png;base64,${newChartData}`;
          img.alt = `Top ${topN} Disease Categories`;
        } else {
          console.error("Image element not found");
        }
      })
      .catch((error) => console.error("Error:", error));
  }
}
function displayHypothesisTest(testResults) {
  const element = document.getElementById("hypothesis-test");
  element.innerHTML = `
        <p>T-statistic: ${testResults.t_statistic}</p>
        <p>P-value: ${testResults.p_value}</p>
    `;
}
