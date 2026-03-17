# copy .pbn files created in the last 2 hours to afterGamesReport
# note: you must manually copy screenshot pngs in ~/Pictures to ./afterGamesReport manually.
find . -name "*.pbn" -type f -mmin -120 -not -path "./afterGamesReport/*" -exec cp {} ./afterGamesReport \;
rm afterGamesReport/precedent.pbn 2>/dev/null 1>/dev/null

