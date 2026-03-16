# ============================================================================
# TFT Set 16 EDA - SQL Analysis from tft_data.db
# Visualizations for carry analysis queries
# ============================================================================

# ---- 1. Load Libraries ----
if (!require("tidyverse")) install.packages("tidyverse", repos = "https://cloud.r-project.org")
if (!require("DBI")) install.packages("DBI", repos = "https://cloud.r-project.org")
if (!require("RSQLite")) install.packages("RSQLite", repos = "https://cloud.r-project.org")
if (!require("scales")) install.packages("scales", repos = "https://cloud.r-project.org")
if (!require("gridExtra")) install.packages("gridExtra", repos = "https://cloud.r-project.org")

library(tidyverse)
library(DBI)
library(RSQLite)
library(scales)
library(gridExtra)

# ---- 2. Connect to SQLite Database ----
cat("Connecting to tft_data.db...\n")
con <- dbConnect(RSQLite::SQLite(), "data/processed/tft_data.db")

# Create output directory
if (!dir.exists("reports/plots")) {
  dir.create("reports/plots", recursive = TRUE)
}

theme_set(theme_minimal(base_size = 12))

# ============================================================================
# QUERY 1: Carry Count Win Rate
# ============================================================================
cat("\n========== CARRY COUNT WIN RATE ==========\n")

query1 <- "
WITH carry_count_per_match AS (
    SELECT 
        puuid,
        match_id,
        COUNT(*) AS carry_count,
        MIN(placement) AS placement
    FROM carries
    GROUP BY puuid, match_id
)
SELECT 
    carry_count,
    COUNT(*) AS total_matches,
    SUM(CASE WHEN placement <= 4 THEN 1 ELSE 0 END) AS total_wins,
    ROUND(
        CAST(SUM(CASE WHEN placement <= 4 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 
        2
    ) AS win_rate_percentage
FROM carry_count_per_match
GROUP BY carry_count
ORDER BY carry_count ASC;
"

carry_count_data <- dbGetQuery(con, query1)
cat("Query 1 Results:\n")
print(carry_count_data)


# Combined plot for carry count
p1_combined <- ggplot(carry_count_data, aes(x = factor(carry_count))) +
  geom_bar(aes(y = total_matches), 
           stat = "identity", fill = "steelblue", alpha = 0.5, width = 0.7) +
  geom_line(aes(y = win_rate_percentage * max(total_matches) / 100, group = 1), color = "red", linewidth = 1.2) +
  geom_point(aes(y = win_rate_percentage * max(total_matches) / 100), color = "red", size = 3) +
  geom_text(aes(y = win_rate_percentage * max(total_matches) / 100, label = paste0(win_rate_percentage, "%")), 
            vjust = -1, color = "black", size = 3.5) +
  geom_text(aes(y = total_matches, 
                label = ifelse(carry_count >= 5, paste0(comma(total_matches)), "")), 
            vjust = -0.5, color = "black", size = 4) +
  scale_y_continuous(
    name = "Total Matches",
    labels = comma,
    sec.axis = sec_axis(~. * 100 / max(carry_count_data$total_matches), 
                        name = "Win Rate (%)")
  ) +
  labs(
    title = "Carry Count: Win Rate vs Match Volume",
    subtitle = "Line = Win Rate, Bars = Match Count (scaled)",
    x = "Number of Carries"
  ) +
  theme(
    plot.title = element_text(face = "bold", size = 14),
    axis.title.y.left = element_text(color = "steelblue"),
    axis.title.y.right = element_text(color = "red")
  )

print(p1_combined)
ggsave("reports/plots/carry_count_with_win_rate.png", p1_combined, width = 12, height = 6)

cat("Saved carry count plots to reports/plots/\n")

# ============================================================================
# QUERY 2: Playstyle Win Rate (Reroll vs Fast Level)
# ============================================================================
cat("\n========== PLAYSTYLE WIN RATE ==========\n")

query2 <- "
SELECT 
    CASE 
        WHEN carry_cost <= 3 THEN 'Reroll'
        WHEN carry_cost > 3 THEN 'Fast Level'
    END AS playstyle,
    COUNT(*) AS total_games,
    SUM(CASE WHEN placement <= 4 THEN 1 ELSE 0 END) AS wins,
    ROUND(
        CAST(SUM(CASE WHEN placement <= 4 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 
        2
    ) AS win_rate
FROM carries
WHERE carry_cost IS NOT NULL
GROUP BY playstyle
ORDER BY win_rate DESC;
"

playstyle_data <- dbGetQuery(con, query2)
cat("Query 2 Results:\n")
print(playstyle_data)

# Plot 2a: Playstyle Win Rate Comparison
p2 <- ggplot(playstyle_data, aes(x = reorder(playstyle, -win_rate), y = win_rate, fill = playstyle)) +
  geom_bar(stat = "identity", width = 0.6, alpha = 0.9) +
  geom_text(aes(label = paste0(win_rate, "%")), vjust = -0.5, size = 5, fontface = "bold") +
  geom_text(aes(label = paste0("total games=", comma(total_games))), vjust = 1.5, size = 4, color = "white") +
  scale_fill_manual(values = c("Reroll" = "#4575b4", "Fast Level" = "#d73027")) +
  labs(
    title = "Win Rate: Reroll vs Fast Level",
    subtitle = "Reroll (cost ≤ 3) vs Fast Level (cost > 3)",
    x = "Playstyle",
    y = "Win Rate (%)",
    caption = "higher is better"
  ) +
  theme(
    plot.title = element_text(face = "bold", size = 14),
    legend.position = "none"
  ) +
  ylim(0, max(playstyle_data$win_rate) * 1.15)

print(p2)
ggsave("reports/plots/playstyle_winrate_comparison.png", p2, width = 8, height = 6)

# ============================================================================
# Query 3 - Top 20 Carries
# ============================================================================
cat("\n========== BONUS: TOP 20 CARRIES ==========\n")

query_bonus <- "
SELECT 
    carry_name,
    COUNT(*) AS total_games,
    SUM(CASE WHEN placement <= 4 THEN 1 ELSE 0 END) AS wins,
    ROUND(
        CAST(SUM(CASE WHEN placement <= 4 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 
        2
    ) AS win_rate
FROM carries
GROUP BY carry_name
HAVING total_games > 50
ORDER BY win_rate DESC
LIMIT 5;
"

top20_carry <- dbGetQuery(con, query_bonus)
top20_carry <- top20_carry %>%
  mutate(carry_name_clean = str_remove(carry_name, "TFT16_|TFT_"))

cat("Top 20 Carries:\n")
print(top20_carry)

# Plot: Top 20 Carries Vertical Bar
p_bonus <- ggplot(top20_carry, aes(x = reorder(carry_name_clean, -win_rate), y = win_rate)) +
  geom_bar(stat = "identity", aes(fill = win_rate), width = 0.8) +
  geom_text(aes(label = paste0(win_rate, "%")), 
            vjust = -0.5, size = 3.5) +
  geom_text(aes(label = paste0("(", total_games, ")")), 
            vjust = 1.5, size = 3, color = "white") +
  scale_fill_gradient2(low = "#4575b4", mid = "#4575b4", high = "#4575b4", 
                       midpoint = 50, name = "Win Rate %") +
  labs(
    title = "Top 5 Carries by Win Rate",
    caption = "Higher is better | Number in parentheses = Total Games",
    x = "Champion",
    y = "Win Rate (%)"
  ) +
  theme(
    plot.title = element_text(face = "bold", size = 14),
    legend.position = "none",
    axis.text.x = element_text(angle = 45, hjust = 1)
  ) +
  ylim(0, max(top20_carry$win_rate) * 1.15)

print(p_bonus)
ggsave("reports/plots/top5_carries.png", p_bonus, width = 12, height = 10)

cat("Saved bonus plot to reports/plots/\n")

# ============================================================================
# SUMMARY DASHBOARD
# ============================================================================
cat("\n========== CREATING SUMMARY DASHBOARD ==========\n")

# Create summary plot combining key insights
summary_text <- paste0(
  "=== TFT SQL Analysis Summary ===\n\n",
  "CARRY COUNT ANALYSIS:\n",
  "• Optimal: ", carry_count_data$carry_count[which.max(carry_count_data$win_rate_percentage)], 
  " carries (", max(carry_count_data$win_rate_percentage), "% win rate)\n",
  "• Most common: ", carry_count_data$carry_count[which.max(carry_count_data$total_matches)],
  " carries (", comma(max(carry_count_data$total_matches)), " matches)\n\n",
  "PLAYSTYLE COMPARISON:\n",
  "• ", playstyle_data$playstyle[1], ": ", playstyle_data$win_rate[1], "% win rate\n",
  "• ", playstyle_data$playstyle[2], ": ", playstyle_data$win_rate[2], "% win rate\n\n",
  "TOP CARRIES:\n",
  paste0("• ", top_carry_data$carry_name_clean, ": ", top_carry_data$win_rate, "%", collapse = "\n")
)

cat(summary_text)

# Save summary to file
writeLines(summary_text, "reports/sql_analysis_summary.txt")
cat("\n\nSummary saved to reports/sql_analysis_summary.txt\n")

# ============================================================================
# CLOSE DATABASE CONNECTION
# ============================================================================
dbDisconnect(con)
cat("\n========== ALL SQL PLOTS SAVED ==========\n")
cat("10 plots exported to reports/plots/sql_*.png\n")
cat("EDA SQL Analysis completed successfully!\n")
