### Using Q-plus Bridge with Two Players

#### **When PCs Are Not Connected**
1. **Player Roles**:
   - South sets themselves as "Human" and North as "Extern" in `Configuration / Players`.
   - North sets themselves as "Human" and South as "Extern".
2. **Synchronization**:
   - Both players select the same deal source, deal numbers, bidding system, playing strength, and lead/signaling conventions.
   - Use `Configuration / Check!` to verify identical setups.
3. **Communication**:
   - Players manually exchange bids and plays during the game.
   - South sees an extra display of possible cards when entering North’s moves.

#### **When PCs Are Connected**
1. **Setup Scenarios**:
   - **Via LAN**: One PC acts as the server, the other as the client.
   - **Via Internet**: Both PCs connect to the Q-plus server with user identification data (full name and address).

2. **LAN Setup**:
   - Server PC:
     - Configure South as "Human" and others as "Computer".
     - Start the bridge server via `Network / Start bridge server`.
     - Allow Windows firewall private network communication.
   - Client PC:
     - Connect to the server via `Network / Connect to local bridge server` with the server’s address.
     - Set North as "Human" and join the game.

3. **Internet Setup**:
   - Both players enter full names and partner data under `File / My user data`.
   - Connect via `Network / Connect to Q-plus bridge server`. Agree on a time for clicking `List` to find and select the desired partner.
   - Select the correct partner and accept the connection to start the game.

---

### Features and Functions

#### **Game Setup**
1. **Bidding Systems**:
   - Configure under `Configuration / Bidding Systems`.
   - Customizable options available.

2. **Lead and Signaling Conventions**:
   - Found under menus `Configuration / Lead Conventions` and `Configuration / Signaling Conventions`.

3. **Playing Strength and Cheating**:
   - Adjust calculation complexity under `Configuration / Playing Strength`.
   - Enable "cheating" mode to view all hands during play.

4. **Game Continuation**:
   - Save and restore matches with `File / Save Match + Exit` and `File / Restore score sheet`.

#### **During Gameplay**
1. **Getting Bidding Information**:
   - Right-click on bids marked with "~ or ." for explanations.
   - Use the `List` button to see possible bids, their meanings, and whether they are forcing or artificial.

2. **Simulation**:
   - Simulate bids to compute outcomes over up to 1,000 deals. Found in the simulation interface when it's your turn.

3. **Trick Analysis**:
   - Click `List` or `Evaluate` during play to calculate expected tricks.
   - Options include "expected tricks with hidden hands" or "open hands" (double dummy play).

4. **Claim or Auto-play**:
   - Use the `Claim` button to finish hands early or `Autoplay` to let the computer complete the deal.

#### **Review and Logs**
1. **Review Completed Deals**:
   - Analyze bids and card play for each deal post-completion via the `Review` button.

2. **Game Logs**:
   - Access logs under `View / Show current log file`.
   - Logs are stored in sequentially numbered files in the installation directory.

---

### Custom Deals and Match Sharing

#### **Creating and Saving Deals**
1. **Deal Creation**:
   - Enter deals manually via `Own Deals / Enter`.
   - Clear prior cards using the `Clear all` button.
   - Assign a unique ID to each deal.

2. **Adding Remarks and Prepared Actions**:
   - Use `View / Edit Remark` to add comments or guidance for specific bids and plays.
   - Prepare predefined actions to enforce correct gameplay or offer teaching aids.

3. **Saving Deals**:
   - Save all entered deals to a file via `Own Deals / Save entered deals to a file`.

#### **Using and Exchanging Deals**
1. **Own Deals**:
   - Load saved deal files under `Own Deals / Use, export and import own deals`.
   - Specify which portion of the deal (cards, bids, lead, or tricks) to read.

2. **Deal Exchange**:
   - Export deals with `Own Deals / Use, export and import own deals > Export to server`.
   - Select public, protected, or private usage.
   - Import deals from other authors under the same menu.

#### **Match Sharing**
1. **Host Steps**:
   - Play a match, save the scoring table, and invite another player via `Matches - my invitations`.
   - Specify the invitee’s name (partial names acceptable).

2. **Invitee Steps**:
   - Accept invitations under `Matches - invitations from other persons`.
   - Play the match and send results back to the inviter.

---

### Special Game Modes

1. **Two Human Players**:
   - Play on one PC or two PCs (connected or standalone).
   - Use `Configuration / Player` to specify roles (Human, Computer, Extern).

2. **MiniBridge Mode**:
   - Simplified version of bridge with direct contract declaration. Activate in `Configuration / Players` or `Extras`.

3. **One Player Mode**:
   - Simulates tournament conditions by only showing one player’s hand. Configure in `Extras / One player mode`.

4. **Visible Hands**:
   - Adjust visibility of cards for teaching or review purposes under `Configuration / Players` or `View / Open all hands`.

---

### Additional Features

1. **Preferences**:
   - Adjust mouse handling, hand displays, and log formats under `Configuration / Preferences`.

2. **Modes of Operation**:
   - **Comparison Against Closed Room**: Play deals simultaneously with computers in another room.
   - **Pairs Tournament**: Compete using pre-recorded tournament results.
   - **Team Tournament**: Play matches based on tournament files.

3. **Printing and Exporting**:
   - Print hands or export them to HTML under `File / Print` or `File / Export to HTML`.

4. **Network Troubleshooting**:
   - If connection issues arise during LAN setup:
     - Use the `ping` command in the client PC to test the server PC's connection.
     - Check firewall settings and ensure communication permissions are enabled.

