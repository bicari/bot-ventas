from pywa import WhatsApp

wa = WhatsApp(
    phone_id='118125007947679',  # The phone id you got from the API Setup
    token='EAAR6yERULLYBPHkeuV3aRnZCZBCtW0RkYssTx4OTO7BsCDmvJntOANocRREVGyR7jZBOIpGaeVtGusSkvZCde9qk4ZBZCMRI2SXI4BHqv9Lhn65XgySrPg2jgUv0Y8foUmJbzeytfM3xKuZAK3wA3xdNQKsmS3ZApStEmeLztn58qe252josZCfCqGxsplcDMokZC5IQZDZD'  # The token you got from the API Setup
)

print(wa.send_message(
    to='584244915022',
    text='Hola soy un bot de prueba, ¿cómo estás?'
))