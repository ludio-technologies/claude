#!/usr/bin/env python3
"""Sound Act Draw! prompt banks — 300 entries per bank.

The bar every entry has to clear:
  * CHANNEL — at least one of sound / act / draw genuinely works.
  * LANDING — a normal room can NAME it once the mime lands.

So: concrete over abstract (no "enshittification", no "situationship"), no
face-only celebrities, no season numbers, no obscure-but-drawable trivia
(nobody shouts "Aye-Aye!"), and a real slice of sound-first cards because the
game is called Sound Act Draw.

`words` is the Standard-edition bank. The four generation banks feed the
Generations edition, where the point is cohort nostalgia — the clue-giver may
well be miming something the guessers never lived through.

Categories are structural, not exported: the game flattens each bank and draws
3 at random. They exist so the mix stays deliberate and is easy to re-balance.
"""

WORDS = {
    # ── Actions & everyday scenes (60) — the best charades cards there are.
    "actions": [
        "Sneezing", "Juggling", "Parallel Parking", "Blowing Out Candles",
        "Tug of War", "Changing a Diaper", "Shoveling Snow", "Hailing a Taxi",
        "Threading a Needle", "Getting a Haircut", "Brushing Your Teeth",
        "Tying Your Shoes", "Doing the Limbo", "Riding a Rollercoaster",
        "Walking a Dog", "Mowing the Lawn", "Flying a Kite", "Blowing Bubbles",
        "Popping a Balloon", "Climbing a Ladder", "Rowing a Boat",
        "Swatting a Fly", "Putting on Makeup", "Wrapping a Present",
        "Carving a Pumpkin", "Building a Sandcastle", "Skipping Rope",
        "Arm Wrestling", "Thumb War", "Doing a Cartwheel", "Slipping on Ice",
        "Stubbing Your Toe", "Missing the Bus", "Waiting in Line",
        "Job Interview", "First Date", "Proposing Marriage",
        "Cutting the Wedding Cake", "Blowing a Bubble Gum Bubble",
        "Taking a Selfie", "Losing Your Keys", "Assembling Furniture",
        "Painting a Wall", "Hanging a Picture", "Doing Laundry",
        "Ironing a Shirt", "Washing the Dishes", "Making the Bed",
        "Hitting Snooze", "Sword Fighting", "Blowing on Hot Soup",
        "Opening a Stuck Jar", "Sharpening a Pencil", "Raking Leaves",
        "Snorkeling", "Tiptoeing", "Piggyback Ride", "Sleepwalking",
        "Fishing", "Bowling",
    ],
    # ── Objects & gadgets (50) — pictionary's bread and butter.
    "objects": [
        "Umbrella", "Toaster", "Lawn Mower", "Snow Globe", "Piñata",
        "Revolving Door", "Trampoline", "Shopping Cart", "Mousetrap",
        "Hammock", "Wheelbarrow", "Vending Machine", "Escalator",
        "Ferris Wheel", "Traffic Light", "Fire Hydrant", "Bunk Bed",
        "Ceiling Fan", "Washing Machine", "Microwave", "Blender",
        "Corkscrew", "Rolling Pin", "Stapler", "Paper Shredder",
        "Metal Detector", "Megaphone", "Binoculars", "Telescope",
        "Magnifying Glass", "Compass", "Hourglass", "Grandfather Clock",
        "Piggy Bank", "Jack-in-the-Box", "Kaleidoscope", "Bouncy Castle",
        "Water Slide", "Diving Board", "Kiddie Pool", "Pogo Stick",
        "Unicycle", "Tandem Bicycle", "Treadmill", "Punching Bag",
        "Bowling Ball", "Dartboard", "Pool Table", "Slot Machine",
        "Claw Machine",
    ],
    # ── Characters, stories & games (40) — universal, no era attached.
    "stories": [
        "Superman", "Batman", "Mickey Mouse", "Snow White", "Cinderella",
        "Peter Pan", "Pinocchio", "The Little Mermaid", "Beauty and the Beast",
        "Alice in Wonderland", "Robin Hood", "King Kong", "Godzilla",
        "Dracula", "Frankenstein", "The Mummy", "Sherlock Holmes", "Tarzan",
        "The Three Little Pigs", "Goldilocks", "Little Red Riding Hood",
        "Humpty Dumpty", "Jack and the Beanstalk", "The Tortoise and the Hare",
        "Zombie Apocalypse", "Chess", "Checkers", "Jenga", "Bingo",
        "Playing Poker", "Hide and Seek", "Musical Chairs", "Duck Duck Goose",
        "Rock Paper Scissors", "Simon Says", "Tic-Tac-Toe", "Crossword Puzzle",
        "Freeze Tag", "Leapfrog", "Piggy in the Middle",
    ],
    # ── Sound-first (35) — the channel the old bank forgot entirely.
    "sounds": [
        "Ambulance Siren", "Chainsaw", "Popcorn Popping", "Thunderstorm",
        "Vacuum Cleaner", "Bagpipes", "Alarm Clock", "Dial-Up Modem",
        "Baby Crying", "Rooster", "Car Alarm", "Fire Alarm", "Doorbell",
        "Church Bells", "Ice Cream Truck", "Train Whistle", "Foghorn",
        "Helicopter", "Motorcycle", "Race Car", "Jackhammer", "Leaf Blower",
        "Snoring", "Hiccups", "Whistling", "Yodeling", "Beatboxing",
        "Opera Singer", "Marching Band", "Drumroll", "Zipper", "Velcro",
        "Bubble Wrap", "Crickets Chirping", "Wolf Howling",
    ],
    # ── Animals (30) — shape-forward, instantly nameable.
    "animals": [
        "Penguin", "Octopus", "Kangaroo", "Elephant", "Flamingo", "T-Rex",
        "Woodpecker", "Skunk", "Giraffe", "Sloth", "Crab", "Snail", "Turtle",
        "Frog", "Owl", "Bat", "Peacock", "Gorilla", "Snake", "Shark",
        "Jellyfish", "Camel", "Hedgehog", "Beaver", "Squirrel", "Chameleon",
        "Seahorse", "Walrus", "Bumblebee", "Praying Mantis",
    ],
    # ── Jobs & characters (25) — a whole person in one gesture.
    "jobs": [
        "Firefighter", "Dentist", "Lifeguard", "Referee", "Astronaut", "Mime",
        "Pirate", "Cowboy", "Ninja", "Knight", "Wizard", "Clown", "Magician",
        "Ballerina", "Sumo Wrestler", "Bodybuilder", "Surgeon", "Barber",
        "Chef", "Waiter", "Mail Carrier", "Construction Worker", "Scuba Diver",
        "Beekeeper", "Mermaid",
    ],
    # ── Food & drink (25)
    "food": [
        "Spaghetti", "Corn on the Cob", "Ice Cream Cone", "Watermelon",
        "Birthday Cake", "Sushi", "Hot Dog", "Pizza Slice", "Taco", "Pretzel",
        "Cotton Candy", "Candy Apple", "Lollipop", "Popsicle", "Banana Split",
        "Pancake Stack", "Fried Egg", "Bacon", "Donut", "Cupcake",
        "Milkshake", "Lemonade", "Champagne Toast", "Toasting Marshmallows",
        "Fortune Cookie",
    ],
    # ── Places & landmarks (20) — silhouettes everybody can draw.
    "places": [
        "Eiffel Tower", "Statue of Liberty", "Great Wall of China",
        "Niagara Falls", "The Pyramids", "Leaning Tower of Pisa", "Big Ben",
        "Mount Everest", "Grand Canyon", "Stonehenge", "Taj Mahal",
        "Golden Gate Bridge", "Sydney Opera House", "Hollywood Sign",
        "Mount Rushmore", "The Colosseum", "Times Square", "The Sahara Desert",
        "The North Pole", "Bermuda Triangle",
    ],
    # ── Idioms & phrases (15) — classic charades fare.
    "idioms": [
        "Raining Cats and Dogs", "Break the Ice", "Cold Feet", "Piece of Cake",
        "Spill the Beans", "Bite the Bullet", "Hit the Hay", "Kick the Bucket",
        "Let the Cat Out of the Bag", "Under the Weather",
        "Butterflies in Your Stomach", "Barking Up the Wrong Tree",
        "Elephant in the Room", "Couch Potato", "Green Thumb",
    ],
}

BOOMER = {
    "people": [
        "Elvis Presley", "The Beatles", "Marilyn Monroe", "Muhammad Ali",
        "Neil Armstrong", "John F Kennedy", "Martin Luther King Jr",
        "Elizabeth Taylor", "Frank Sinatra", "Bob Dylan", "Jimi Hendrix",
        "Janis Joplin", "John Lennon", "Mick Jagger", "Cher", "Dolly Parton",
        "Johnny Cash", "Aretha Franklin", "Stevie Wonder", "Diana Ross",
        "James Brown", "Ray Charles", "Barbra Streisand", "Tina Turner",
        "Bob Marley", "Jim Morrison", "Jerry Garcia", "Paul McCartney",
        "Ringo Starr", "Audrey Hepburn", "Sophia Loren", "Clint Eastwood",
        "John Wayne", "Paul Newman", "Steve McQueen", "Sean Connery",
        "Sidney Poitier", "Jack Nicholson", "Robert Redford", "Dustin Hoffman",
        "Al Pacino", "Marlon Brando", "Alfred Hitchcock", "Julie Andrews",
        "Judy Garland", "Lucille Ball", "Carol Burnett", "Johnny Carson",
        "Walter Cronkite", "Julia Child", "Queen Elizabeth", "Richard Nixon",
        "Jackie Kennedy", "Andy Warhol", "Pablo Picasso", "Salvador Dali",
        "Dr Seuss", "Charlie Chaplin", "Buster Keaton", "Fred Astaire",
        "Gene Kelly", "Dean Martin", "Bing Crosby", "Louis Armstrong",
        "Ella Fitzgerald", "Chuck Berry", "Little Richard", "Buddy Holly",
        "The Rolling Stones", "The Beach Boys", "Simon and Garfunkel",
        "Jane Fonda", "Farrah Fawcett", "Evel Knievel", "Joe Namath",
        "Jackie Robinson", "Arnold Palmer", "Billie Jean King", "Bruce Lee",
        "Yoko Ono",
    ],
    "screen": [
        "Jaws", "The Godfather", "Star Trek", "The Wizard of Oz", "Psycho",
        "2001: A Space Odyssey", "Gone with the Wind", "Casablanca", "Ben-Hur",
        "Lawrence of Arabia", "The Sound of Music", "Mary Poppins",
        "West Side Story", "Singin' in the Rain", "The Graduate",
        "Bonnie and Clyde", "Easy Rider", "Butch Cassidy and the Sundance Kid",
        "The Exorcist", "Rocky", "A Clockwork Orange", "Taxi Driver",
        "One Flew Over the Cuckoo's Nest", "Planet of the Apes",
        "Dr Strangelove", "The Great Escape", "The Magnificent Seven",
        "True Grit", "The French Connection", "Chinatown", "The Sting",
        "Cool Hand Luke", "To Kill a Mockingbird", "Breakfast at Tiffany's",
        "Some Like It Hot", "Rear Window", "Vertigo", "North by Northwest",
        "The Birds", "Willy Wonka", "Young Frankenstein", "Blazing Saddles",
        "The Pink Panther", "The Rocky Horror Picture Show", "James Bond",
        "Goldfinger", "Barbarella", "The Ten Commandments", "Spartacus",
        "Cleopatra", "I Love Lucy", "The Twilight Zone", "Bewitched",
        "I Dream of Jeannie", "The Brady Bunch", "Gilligan's Island",
        "The Addams Family", "The Munsters", "Scooby-Doo", "The Flintstones",
        "The Jetsons", "Looney Tunes", "Bugs Bunny", "Tom and Jerry",
        "Popeye", "Batman TV Show", "The Lone Ranger", "Bonanza", "Gunsmoke",
        "Hogan's Heroes", "The Andy Griffith Show", "Get Smart",
        "Mission Impossible", "Doctor Who", "American Bandstand", "Soul Train",
        "The Price Is Right", "Jeopardy", "Mister Rogers", "Captain Kangaroo",
        "Howdy Doody", "Laugh-In", "All in the Family", "M*A*S*H",
        "The Mary Tyler Moore Show", "Happy Days", "Laverne and Shirley",
        "Three's Company", "Charlie's Angels", "The Six Million Dollar Man",
        "Kojak", "Columbo", "The Waltons", "Little House on the Prairie",
        "Dallas", "Fantasy Island", "The Love Boat", "Green Acres",
        "The Honeymooners", "Perry Mason",
    ],
    "stuff": [
        "Hula Hoop", "Lava Lamp", "Slinky", "8-Track Tape", "Rotary Phone",
        "TV Dinner", "Drive-In Movie", "Bell Bottoms", "Woodstock",
        "Moon Landing", "Jukebox", "Tie-Dye", "Yo-Yo", "Etch A Sketch",
        "Magic 8 Ball", "Mr Potato Head", "Barbie Doll", "GI Joe", "Play-Doh",
        "Lego", "Twister", "Erector Set", "Lincoln Logs", "View-Master",
        "Slip 'N Slide", "Roller Skates", "Banana Seat Bike", "Big Wheel",
        "Radio Flyer Wagon", "Hot Wheels", "Matchbox Cars", "Pinball Machine",
        "Pong", "Skee-Ball", "Bowling Alley", "Soda Fountain", "Malt Shop",
        "Poodle Skirt", "Leather Jacket", "Beehive Hairdo", "Afro",
        "Sideburns", "Go-Go Boots", "Miniskirt", "Platform Shoes",
        "Leisure Suit", "Peace Sign", "Flower Power", "Love Beads",
        "Headband", "Fringe Vest", "VW Bus", "VW Beetle", "Muscle Car",
        "Convertible", "Roadside Motel", "Route 66", "Station Wagon",
        "Hitchhiking", "CB Radio", "Transistor Radio", "Record Player",
        "Vinyl Record", "Hi-Fi Stereo", "Reel-to-Reel Tape",
        "Polaroid Camera", "Home Movie Projector", "Rabbit Ear Antenna",
        "Color Television", "Telephone Booth", "Rotary Dial", "Typewriter",
        "Mimeograph", "Chalkboard", "Slide Rule", "Card Catalog",
        "Encyclopedia Set", "Milk Man", "Paper Boy", "Soda Jerk",
        "Bomb Shelter", "Duck and Cover Drill", "Sputnik", "Apollo Rocket",
        "Astronaut Suit", "Ham Radio", "Microwave Oven", "Coffee Percolator",
        "Fondue Pot", "Jell-O Mold", "TV Tray", "Shag Carpet",
        "Wood Paneling", "Waterbed", "Beanbag Chair", "Disco Ball",
        "Roller Disco", "Sock Hop", "Soap Box Derby", "Little League",
        "Girl Scout Cookies", "Lemonade Stand", "Paper Route", "Jacks",
        "Marbles", "Cat's Cradle", "Kick the Can", "Red Rover", "Tetherball",
        "Dodgeball", "Four Square", "Pet Rock", "Chia Pet", "Silly Putty",
        "Berlin Wall", "Bomb Pop", "Drive-In Diner", "Cadillac Fins",
        "Poodle Perm", "Chewing Gum Cigarettes",
    ],
}

GENX = {
    "people": [
        "Michael Jackson", "Madonna", "Prince", "Michael Jordan",
        "Whitney Houston", "Freddie Mercury", "David Bowie",
        "Bruce Springsteen", "Cyndi Lauper", "Boy George", "Run-DMC",
        "Beastie Boys", "MC Hammer", "Vanilla Ice", "Snoop Dogg",
        "Tupac Shakur", "Notorious BIG", "Kurt Cobain", "Axl Rose",
        "Ozzy Osbourne", "Bon Jovi", "Metallica", "Aerosmith", "Van Halen",
        "George Michael", "Phil Collins", "Janet Jackson", "Paula Abdul",
        "Milli Vanilli", "Salt-N-Pepa", "Weird Al Yankovic", "Rick Astley",
        "Tom Cruise", "Tom Hanks", "Eddie Murphy", "Robin Williams",
        "Jim Carrey", "Arnold Schwarzenegger", "Sylvester Stallone",
        "Bruce Willis", "Harrison Ford", "Kevin Costner", "Patrick Swayze",
        "Keanu Reeves", "Winona Ryder", "Julia Roberts", "Demi Moore",
        "Michelle Pfeiffer", "Meg Ryan", "Molly Ringwald", "Jodie Foster",
        "Sigourney Weaver", "Whoopi Goldberg", "Macaulay Culkin",
        "Pee-wee Herman", "Mr T", "Hulk Hogan", "Andre the Giant",
        "Mike Tyson", "Magic Johnson", "Larry Bird", "Wayne Gretzky",
        "Carl Lewis", "Mary Lou Retton", "John McEnroe", "Andre Agassi",
        "Bo Jackson", "Joe Montana", "Bill Gates", "Steve Jobs",
        "Oprah Winfrey", "David Letterman", "Jay Leno", "Arsenio Hall",
        "Bob Ross", "Richard Simmons", "Princess Diana", "Ronald Reagan",
        "Margaret Thatcher", "Nelson Mandela",
    ],
    "screen": [
        "Star Wars", "The Empire Strikes Back", "Return of the Jedi", "E.T.",
        "Ghostbusters", "Back to the Future", "Indiana Jones",
        "Raiders of the Lost Ark", "Top Gun", "The Breakfast Club",
        "Ferris Bueller's Day Off", "Sixteen Candles", "Pretty in Pink",
        "Dirty Dancing", "Footloose", "Flashdance", "Grease",
        "The Karate Kid", "The Goonies", "Stand by Me", "Gremlins",
        "Beetlejuice", "Ghost", "Big", "Home Alone", "Die Hard",
        "Lethal Weapon", "RoboCop", "The Terminator", "Predator", "Alien",
        "Aliens", "Blade Runner", "Mad Max", "Rambo", "Batman 1989",
        "Beverly Hills Cop", "Coming to America", "Trading Places",
        "Airplane", "The Naked Gun", "Caddyshack", "Animal House",
        "Spaceballs", "The Princess Bride", "Labyrinth",
        "The NeverEnding Story", "Willow", "Short Circuit",
        "Weird Science", "Bill and Ted", "Wayne's World", "Groundhog Day",
        "Pulp Fiction", "Forrest Gump", "Jurassic Park",
        "The Silence of the Lambs", "Thelma and Louise",
        "When Harry Met Sally", "Nightmare on Elm Street", "Friday the 13th",
        "Halloween", "Poltergeist", "The Shining", "Scarface", "Miami Vice",
        "Magnum PI", "Knight Rider", "The A-Team", "MacGyver", "Full House",
        "Family Ties", "Growing Pains", "The Cosby Show", "Cheers",
        "Seinfeld", "Married with Children", "Roseanne", "The Wonder Years",
        "Saved by the Bell", "Beverly Hills 90210", "Twin Peaks",
        "The X-Files", "Baywatch", "The Simpsons", "Beavis and Butt-Head",
        "Ren and Stimpy", "He-Man", "She-Ra", "Transformers", "ThunderCats",
        "Teenage Mutant Ninja Turtles", "Care Bears", "My Little Pony",
        "Smurfs", "The Muppets", "Fraggle Rock", "Sesame Street", "MTV",
        "Saturday Night Live",
    ],
    "stuff": [
        "Walkman", "Rubik's Cube", "Boombox", "Pac-Man", "Cassette Tape",
        "Mixtape", "Mullet", "Shoulder Pads", "Slap Bracelet",
        "Trapper Keeper", "VHS Tape", "Roller Rink", "Big Hair",
        "Aqua Net Hairspray", "Perm", "Members Only Jacket",
        "Parachute Pants", "Acid Wash Jeans", "Leg Warmers", "Jelly Shoes",
        "Jelly Bracelets", "Scrunchie", "Neon Windbreaker", "Swatch Watch",
        "Ray-Bans", "Fanny Pack", "Doc Martens", "Converse High Tops",
        "Air Jordans", "Reebok Pumps", "Jams Shorts",
        "Hypercolor Shirt", "Friendship Bracelet", "Puffy Paint",
        "Lisa Frank Folder", "Trolls Doll", "Cabbage Patch Kids",
        "Garbage Pail Kids", "Pound Puppies", "Rainbow Brite", "Glo Worm",
        "Teddy Ruxpin", "Speak and Spell", "Simon Game", "Lite-Brite",
        "Spirograph", "Operation Game", "Hungry Hungry Hippos", "Perfection",
        "Connect Four", "Battleship", "Trivial Pursuit", "Pictionary",
        "Guess Who", "Mouse Trap Game", "Nintendo Entertainment System",
        "Super Mario Bros", "Duck Hunt Gun", "The Legend of Zelda", "Tetris",
        "Atari", "Atari Joystick", "Sega Genesis", "Arcade Cabinet",
        "Donkey Kong", "Frogger", "Space Invaders", "Asteroids", "Centipede",
        "Galaga", "Skateboarding", "BMX Bike", "Rollerblades", "Aerobics",
        "Jazzercise", "Jane Fonda Workout", "Thighmaster", "Sony Discman",
        "Betamax", "Laserdisc", "VCR", "Blockbuster Video", "Be Kind Rewind",
        "Camcorder", "Answering Machine", "Pager", "Car Phone",
        "Brick Cell Phone", "Fax Machine", "Dot Matrix Printer",
        "Commodore 64", "Apple Macintosh", "Oregon Trail",
        "Overhead Projector", "Microwave Popcorn", "Tang", "Kool-Aid Man",
        "Pop Rocks", "New Coke", "Jolt Cola", "Slurpee", "Push Pop",
        "Ring Pop", "Big League Chew", "Cracker Jack",
        "Pixy Stix", "Nerds", "Mall Food Court", "Spencer's Gifts",
        "Payphone", "Break Dancing", "The Moonwalk", "Robot Dance",
        "The Running Man", "Mosh Pit", "Grunge Flannel", "Where's Waldo",
        "Magic Eye Poster", "Koosh Ball", "Super Soaker",
    ],
}

MILLENNIAL = {
    "people": [
        "Britney Spears", "Christina Aguilera", "Justin Timberlake", "NSYNC",
        "Backstreet Boys", "Spice Girls", "Destiny's Child", "Beyoncé",
        "Eminem", "50 Cent", "Jay-Z", "Kanye West", "Rihanna", "Lady Gaga",
        "Katy Perry", "Avril Lavigne", "Green Day", "Blink-182",
        "Linkin Park", "Coldplay", "Amy Winehouse", "Adele", "Mariah Carey",
        "Shakira", "Ricky Martin", "Jennifer Lopez", "Usher", "Alicia Keys",
        "OutKast", "Missy Elliott", "Lil Wayne", "Leonardo DiCaprio",
        "Kate Winslet", "Will Smith", "Adam Sandler", "Ben Stiller",
        "Owen Wilson", "Steve Carell", "Tina Fey", "Amy Poehler",
        "Seth Rogen", "Jonah Hill", "Anne Hathaway", "Reese Witherspoon",
        "Cameron Diaz", "Drew Barrymore", "Sandra Bullock", "Angelina Jolie",
        "Brad Pitt", "Johnny Depp", "Jennifer Aniston", "Matthew Perry",
        "Sarah Jessica Parker", "Lindsay Lohan", "Paris Hilton",
        "Kim Kardashian", "Hilary Duff", "The Olsen Twins", "Zac Efron",
        "Daniel Radcliffe", "Emma Watson", "Tiger Woods",
        "Serena Williams", "David Beckham", "Michael Phelps", "Usain Bolt",
        "Shaquille O'Neal", "Kobe Bryant", "LeBron James", "Tom Brady",
        "Roger Federer", "Rafael Nadal", "Tony Hawk", "Steve Irwin",
        "Simon Cowell", "Ryan Seacrest", "Jon Stewart", "Mark Zuckerberg",
        "Barack Obama", "Gordon Ramsay",
    ],
    "screen": [
        "Harry Potter", "Shrek", "Titanic", "Friends", "The Office",
        "SpongeBob SquarePants", "Pokémon", "The Matrix",
        "The Lord of the Rings", "Pirates of the Caribbean", "Finding Nemo",
        "Toy Story", "Monsters Inc", "The Incredibles", "Up", "Wall-E",
        "Ratatouille", "Cars", "Madagascar", "Ice Age", "Mean Girls",
        "Legally Blonde", "Bring It On", "10 Things I Hate About You",
        "American Pie", "Superbad", "The Hangover", "Anchorman",
        "Napoleon Dynamite", "Zoolander", "Old School", "Wedding Crashers",
        "School of Rock", "Elf", "Love Actually", "The Notebook", "Twilight",
        "Spider-Man", "X-Men", "Iron Man", "The Dark Knight", "Avatar",
        "Inception", "Slumdog Millionaire", "Juno", "Little Miss Sunshine",
        "Donnie Darko", "Fight Club", "American Beauty", "Memento",
        "Kill Bill", "Ocean's Eleven", "Catch Me If You Can", "Cast Away",
        "The Sixth Sense", "The Ring", "Saw", "Scary Movie", "Austin Powers",
        "Rush Hour", "Men in Black", "Independence Day", "Armageddon",
        "Gladiator", "Lost", "24", "Prison Break", "Grey's Anatomy", "House",
        "ER", "CSI", "Law and Order", "The Sopranos", "The Wire",
        "Breaking Bad", "Mad Men", "Dexter", "Scrubs",
        "How I Met Your Mother", "Arrested Development",
        "Parks and Recreation", "30 Rock", "South Park", "Family Guy",
        "Futurama", "Rugrats", "Hey Arnold", "Recess",
        "The Powerpuff Girls", "Kim Possible", "Lizzie McGuire",
        "Boy Meets World", "Sabrina the Teenage Witch", "Sex and the City",
        "Gilmore Girls", "Dawson's Creek", "Buffy the Vampire Slayer",
        "American Idol", "Survivor", "Fear Factor", "Jackass",
        "Game of Thrones",
    ],
    "stuff": [
        "Tamagotchi", "Game Boy", "Nokia Brick Phone", "Beanie Babies",
        "Heelys", "Razor Scooter", "Frosted Tips", "Livestrong Bracelet",
        "AIM Away Message", "Flip Phone", "Silly Bandz", "iPod", "Furby",
        "Pokémon Cards", "Yu-Gi-Oh Cards", "Pogs", "Beyblade", "Bop It",
        "Polly Pocket", "Bratz Doll", "American Girl Doll", "Tickle Me Elmo",
        "Nintendo 64", "GameCube", "PlayStation", "PlayStation 2", "Xbox",
        "Nintendo Wii", "Guitar Hero", "Rock Band",
        "Dance Dance Revolution", "The Sims", "Neopets", "Club Penguin",
        "Runescape", "MySpace", "Farmville", "Angry Birds", "Fruit Ninja",
        "Temple Run", "Snake on Nokia", "T9 Texting", "Sidekick Phone",
        "BlackBerry", "iPod Shuffle", "Zune", "Napster", "LimeWire",
        "Burned CD", "CD Binder", "Compact Disc", "Portable DVD Player",
        "DVD Box Set", "Netflix DVD Envelope", "AOL Free Trial CD",
        "Chatroom", "Screen Name", "Emo Haircut", "Skinny Jeans",
        "Ugg Boots", "Von Dutch Hat", "Juicy Couture Tracksuit",
        "Ed Hardy Shirt", "Butterfly Hair Clips", "Chunky Highlights",
        "Body Glitter", "Abercrombie Store", "Hot Topic", "Limited Too",
        "Cinnabon", "Orange Julius", "Jamba Juice", "Frappuccino",
        "Red Bull", "Monster Energy", "Smirnoff Ice", "Capri Sun",
        "Lunchables", "Dunkaroos", "Fruit by the Foot", "Gushers",
        "Bagel Bites", "Hot Pockets", "Easy Mac", "Toaster Strudel",
        "Pop-Tarts", "Go-Gurt", "String Cheese", "Sunny D", "Segway",
        "Crocs", "Shutter Shades", "Trucker Hat", "Popped Collar",
        "Cargo Shorts", "Webkinz", "Rainbow Loom", "Silly Putty Egg",
        "Planking", "Rickroll", "Nyan Cat", "Keyboard Cat", "Harlem Shake",
        "Ice Bucket Challenge", "Gangnam Style", "Charlie Bit My Finger",
        "Numa Numa", "Chocolate Rain", "Grumpy Cat", "Doge",
        "Mario Kart", "Call of Duty", "Grand Theft Auto", "Halo",
        "Minesweeper", "Solitaire", "Screensaver", "Clippy",
    ],
}

GENZ = {
    "people": [
        "Taylor Swift", "MrBeast", "Cristiano Ronaldo", "Lionel Messi",
        "Billie Eilish", "Zendaya", "Timothée Chalamet", "Olivia Rodrigo",
        "Harry Styles", "Bad Bunny", "Doja Cat", "Ariana Grande", "Dua Lipa",
        "The Weeknd", "Drake", "Travis Scott", "Post Malone", "Lil Nas X",
        "Cardi B", "Nicki Minaj", "Megan Thee Stallion", "SZA",
        "Kendrick Lamar", "Sabrina Carpenter", "Chappell Roan", "Ice Spice",
        "BTS", "Blackpink", "Charli XCX", "Justin Bieber", "Selena Gomez",
        "Miley Cyrus", "Charli D'Amelio",
        "Addison Rae", "Khaby Lame", "PewDiePie", "Jake Paul",
        "KSI", "Emma Chamberlain", "IShowSpeed", "Kai Cenat",
        "Tom Holland", "Florence Pugh", "Sydney Sweeney", "Jenna Ortega",
        "Millie Bobby Brown", "Finn Wolfhard",
        "Margot Robbie", "Ryan Gosling", "Pedro Pascal", "Simone Biles",
        "Coco Gauff", "Steph Curry", "Patrick Mahomes", "Caitlin Clark",
        "Kylian Mbappé", "Shohei Ohtani", "Elon Musk",
        "Greta Thunberg", "Kylie Jenner",
    ],
    "screen": [
        "Stranger Things", "Squid Game", "Minecraft", "Fortnite", "Among Us",
        "Frozen", "Spider-Verse", "Wednesday", "Euphoria", "Riverdale",
        "Outer Banks",
        "The Witcher", "The Mandalorian", "Baby Yoda", "WandaVision", "Loki",
        "Black Panther", "Avengers Endgame", "Guardians of the Galaxy",
        "Deadpool", "Joker", "Dune", "The Barbie Movie", "Oppenheimer",
        "Everything Everywhere All at Once", "Get Out", "Us", "Nope",
        "Hereditary", "Midsommar", "A Quiet Place", "Bird Box", "It",
        "Five Nights at Freddy's", "Coraline", "Spirited Away",
        "My Hero Academia", "Attack on Titan", "Demon Slayer", "Naruto",
        "One Piece", "Death Note", "Jujutsu Kaisen", "Studio Ghibli",
        "Encanto", "Moana", "Coco", "Inside Out", "Zootopia", "Big Hero 6",
        "Wreck-It Ralph", "Tangled", "Brave", "Luca", "Turning Red", "Soul",
        "Sing", "Despicable Me", "Minions", "The Secret Life of Pets",
        "Trolls", "Paw Patrol", "Peppa Pig", "Bluey", "Cocomelon",
        "Gravity Falls", "Adventure Time", "Steven Universe", "Regular Show",
        "Phineas and Ferb", "Teen Titans Go", "Miraculous Ladybug",
        "Rick and Morty", "Bob's Burgers", "BoJack Horseman", "The Good Place",
        "Brooklyn Nine-Nine", "Ted Lasso", "The Bear", "Succession",
        "The Last of Us", "House of the Dragon", "Love Island",
        "Love Is Blind", "Too Hot to Handle", "Selling Sunset", "Queer Eye",
        "The Great British Bake Off", "Drag Race", "Tiger King", "Roblox",
        "Overwatch", "League of Legends", "Animal Crossing", "Wordle",
        "Flappy Bird", "Pokémon Go", "Rocket League", "Fall Guys",
        "Kung Fu Panda",
    ],
    "stuff": [
        "Fidget Spinner", "Pop It", "Squishmallow", "Slime", "Kinetic Sand",
        "LOL Surprise Doll", "Bottle Flip", "Hoverboard", "Electric Scooter",
        "Skateboard", "Ring Light", "Selfie Stick", "Phone Tripod", "GoPro",
        "Drone", "Instant Camera", "Disposable Camera", "AirPods",
        "Noise-Cancelling Headphones", "Apple Watch", "Fitbit",
        "Hydro Flask", "Stanley Cup", "Reusable Straw", "Boba Tea",
        "Matcha Latte", "Iced Coffee", "Energy Drink", "Takis",
        "Hot Cheetos", "Mukbang", "Instant Ramen", "Poke Bowl", "Açaí Bowl",
        "Avocado Toast", "Charcuterie Board", "Dubai Chocolate",
        "Sourdough Loaf", "Air Fryer", "Instant Pot", "Espresso Machine",
        "Milk Frother", "Pumpkin Spice Latte", "Crocs with Charms",
        "Birkenstocks", "Air Force Ones", "Cargo Pants", "Baggy Jeans",
        "Bucket Hat", "Oversized Hoodie", "Claw Clip", "Acrylic Nails",
        "Sheet Face Mask", "Gua Sha", "Lip Gloss", "Tesla", "Cybertruck",
        "Self-Driving Car", "Charging Station", "Uber Ride", "Airbnb",
        "Amazon Package", "Food Delivery Bag", "QR Code Menu",
        "Tap to Pay", "Bitcoin", "Robot Vacuum", "Smart Speaker",
        "Video Doorbell", "VR Headset", "Robot Dog", "ChatGPT",
        "AI Selfie", "Zoom Call", "Green Screen", "Podcast Microphone",
        "Gaming Chair", "RGB Keyboard", "Twitch Stream", "Speedrun",
        "Battle Royale", "Loot Box", "Emote Dance", "Victory Dance",
        "Escape Room", "Pickleball", "Padel", "Axe Throwing",
        "Trampoline Park", "Rage Room", "Silent Disco", "Music Festival",
        "Coachella", "Festival Wristband", "Crowd Surfing", "Glow Stick",
        "Confetti Cannon", "Photo Booth", "Peloton", "Home Gym",
        "Resistance Band", "Foam Roller", "Massage Gun", "Cold Plunge",
        "Infrared Sauna", "Protein Shake", "Gym Selfie", "Weighted Blanket",
        "LED Strip Lights", "Galaxy Projector", "Mushroom Lamp",
        "Scented Candle", "Bath Bomb", "Onesie Pajamas", "Ugly Sweater",
        "Renegade Dance", "The Griddy", "The Dab", "The Floss",
        "Whip and Nae Nae", "Mannequin Challenge", "Puppy Yoga", "Cat Café",
        "Thrift Haul", "Vinyl Revival", "Mechanical Keyboard",
        "Curved Monitor", "3D Printer", "Electric Bike", "Wireless Charger",
        "Portable Blender", "Northern Lights",
        "Capybara", "Axolotl", "Red Panda", "Quokka", "Highland Cow",
        "Rubber Duck", "Duct Tape Wallet", "Tote Bag",
    ],
}

BANKS = {
    "words": WORDS,
    "boomerCards": BOOMER,
    "genXCards": GENX,
    "millenialCards": MILLENNIAL,
    "genZCards": GENZ,
}


def flatten(bank):
    out = []
    for entries in bank.values():
        out.extend(entries)
    return out


def build():
    """Flatten, then hard-check: 300 per bank, no dupes within or across."""
    banks = {name: flatten(b) for name, b in BANKS.items()}
    problems = []
    seen = {}
    for name, entries in banks.items():
        if len(entries) != 300:
            problems.append("%s has %d entries, expected 300" % (name, len(entries)))
        for e in entries:
            if e in seen:
                problems.append("%r appears in both %s and %s" % (e, seen[e], name))
            seen[e] = name
    return banks, problems


if __name__ == "__main__":
    banks, problems = build()
    for name, entries in banks.items():
        counts = ", ".join("%s %d" % (k, len(v)) for k, v in BANKS[name].items())
        print("%-16s %3d  (%s)" % (name, len(entries), counts))
    print()
    if problems:
        print("PROBLEMS (%d):" % len(problems))
        for p in problems:
            print("  " + p)
    else:
        print("clean: 5 banks x 300, no duplicates within or across banks")
