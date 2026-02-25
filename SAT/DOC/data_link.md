# Summarize, focusing on the keystrokes and button presses needed to evoke each command, along with...
Exported on 05/01/2025 at 10:56:54 [from Perplexity.ai](https://www.perplexity.ai/search/summarize-focusing-on-the-keys-F46cSLfiTpKQbek.1JvY2A) - with [SaveMyChatbot](https://save.hugocollin.com)


## User
summarize, focusing on the keystrokes and button presses needed to evoke each command, along with what the command does:

## AI answer
Here is a summary of the **keystrokes**, **button presses**, and their corresponding **commands/functions** for utilizing the Datalink system in Falcon 4 BMS:

1\. **Hosting the Datalink**
----------------------------

*   **Purpose**: Enable visibility of flight members on the HSD (Horizontal Situation Display).
*   **Steps**:
    
    *   Change the FCR (Fire Control Radar) mode from 'ASSIGN' to 'CONT':
        
        *   On the left MFD, select the option labeled "ASSIGN" on the right side and switch it to "CONT."
        
    *   Press and hold **CTRL + O** for about 2 seconds, then release.
        
        *   **Outcome**: The "CONT" option lights up white, and all aircraft in the flight appear on the HSD.
        
    

2\. **Adding Other Flights to Datalink**
----------------------------------------

*   **Purpose**: Add aircraft outside your immediate flight for enhanced situational awareness.
*   **Steps**:
    
    1.  **Access the LIST menu**:
        
        *   Press **LIST** on the ICP (Integrated Control Panel).
        
    2.  **Navigate to Interflight Datalink**:
        
        *   Press **SEQ** on the ICP rocker until the interflight Datalink page appears.
        
    3.  **Assign Additional Aircraft**:
        
        *   Use the ICP rocker to move to a blank slot.
        *   Input the flight number, e.g., **1-1** (flight lead of package 1), then press **ENTER**.
        *   Repeat as needed for other flight leads (e.g., **2-1**, **3-1**, etc.).
        
    
    *   **Outcome**: Added aircraft appear on the HSD and FCR, showing positional data.
    

3\. **Assigning Air Contacts**
------------------------------

*   **Purpose**: Assign specific air targets to flight members.
*   **Steps**:
    
    1.  Lock the target on the FCR.
    2.  On the right side of the FCR, find the Datalink mode with numbers **1, 2, 3, 4** corresponding to flight members.
    3.  Press the desired number (e.g., **2** to assign the locked target to wingman 2).
    
    *   **Outcome**:
        
        *   The word "TRANSMIT" appears temporarily, confirming the assignment.
        *   Flight members’ HUD displays "ASSIGNED," and the target is visible on their HSD and FCR.
        
    

4\. **Sharing Ground Contact Positions**
----------------------------------------

*   **Purpose**: Transmit ground target data (cursor or mark points) to flight members.
*   **Steps** (Using Air-to-Ground Radar - FCR as Sensor of Interest):
    
    1.  Slew the cursor over a ground target.
    2.  Press **Right CTRL + P** to transmit the position.
    
    *   **Outcome**:
        
        *   A small yellow star with your flight number appears on their HSD, denoting the shared ground contact.
        
    

5\. **Sharing Mark Points or Steer Points**
-------------------------------------------

*   **Purpose**: Digitally share mark points or steer points for precise targeting.
*   **Steps**:
    
    1.  Make the HSD the Sensor of Interest:
        
        *   Press **DMS Down** until the HSD is selected.
        
    2.  Select a Mark Point or Steer Point:
        
        *   Press **STEERPOINT** on the ICP, enter the desired number (e.g., **71** for the first mark point), and press **ENTER**.
        
    3.  Transmit the Mark/Steer Point:
        
        *   Press **Right CTRL + P**.
        *   **Outcome**:
            
            *   The mark point is transmitted to all flight members, appearing on their HUD as "MARK 71" and on their HSD as a blue cross.
            
        
    

6\. **Creating and Sharing Mark Points**
----------------------------------------

*   **Purpose**: Mark and share new ground targets dynamically without prior knowledge of their latitude/longitude.
*   **Steps** (Using FCR as Sensor of Interest):
    
    1.  Access the "MARK" menu on the ICP:
        
        *   Press **7 (MARK)** to open the Mark menu.
        
    2.  Select a Sensor for Marking (e.g., FCR):
        
        *   Press **MARK** repeatedly until "FCR" is displayed.
        
    3.  Create a Mark Point:
        
        *   Slew the cursor over the desired target and press **TMS Up**.
        *   The Mark Point will be saved (e.g., "MARK 27").
        
    4.  Transmit the Mark Point:
        
        *   Ensure HSD is selected as the Sensor of Interest (**DMS Down**) and press **Right CTRL + P**.
        *   **Outcome**:
            
            *   Flight members receive the new mark point on their HUD and HSD.
            
        
    

7\. **Other Useful Controls**
-----------------------------

*   **Switch Steer Points**:
    
    *   Quickly jump to a specific steer point: Press **STEERPOINT** on the ICP, input the number, and press **ENTER.**
    
*   **Overfly Mark Creation**:
    
    *   Set a mark point at your current position: Select "OVERFLY" in the MARK menu and press **TMS Up**.
    

Key Keystrokes/Button Summary:
------------------------------

1.  **CTRL + O**: Host Datalink.
2.  **LIST > SEQ**: Navigate Datalink menus on the ICP.
3.  **Right CTRL + P**: Transmit target data, mark points, or steer points.
4.  **TMS Up**: Create a mark point at the cursor.
5.  **DMS Down**: Change Sensor of Interest to the HSD.
6.  **STEERPOINT + (Number) + ENTER**: Jump to a specific steer point.

This guide condenses the critical steps needed to utilize Datalink in Falcon 4 BMS effectively. Let me know if you need additional clarification!
